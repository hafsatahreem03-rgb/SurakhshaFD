"""Clearance workflow with two-person approval.

1. Institution requests clearance (see fdrs.py).  2. Officer recommends approve/reject.
3. A DIFFERENT senior approver records the final decision with mandatory remarks.

A demo approval only records a decision in this application. It does NOT release any bank funds.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..database import get_db
from ..models import ApprovalDecision, ClearanceRequest, ClearanceStatus, FDRRecord, Role, User, utcnow
from ..schemas import DecideIn, RecommendIn, clearance_out
from ..security import REVIEWER_ROLES, get_current_user, require_roles
from ..services.notify import notify_institution, notify_staff
from ..services.workflow import clearance_eligibility

router = APIRouter(prefix="/api/clearance-requests", tags=["clearance"])


def _load(db: Session, cr_id: int, user: User) -> ClearanceRequest:
    cr = db.get(ClearanceRequest, cr_id)
    if cr is None or (user.role == Role.INSTITUTION and cr.fdr.institution_id != user.institution_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clearance request not found.")
    return cr


@router.get("")
def list_requests(status_filter: str | None = Query(None, alias="status"),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(ClearanceRequest).join(FDRRecord).order_by(ClearanceRequest.created_at.desc())
    if user.role == Role.INSTITUTION:
        stmt = stmt.where(FDRRecord.institution_id == user.institution_id)
    if status_filter == "awaiting_decision":
        stmt = stmt.where(ClearanceRequest.status.in_(
            (ClearanceStatus.RECOMMENDED_APPROVAL, ClearanceStatus.RECOMMENDED_REJECTION)))
    elif status_filter == "decided":
        stmt = stmt.where(ClearanceRequest.status.in_((ClearanceStatus.APPROVED, ClearanceStatus.REJECTED)))
    elif status_filter:
        stmt = stmt.where(ClearanceRequest.status == status_filter)
    return [clearance_out(c, include_fdr=True) for c in db.execute(stmt).scalars()]


@router.get("/{cr_id}")
def get_request(cr_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cr = _load(db, cr_id, user)
    out = clearance_out(cr, include_fdr=True)
    out["current_eligibility"] = clearance_eligibility(db, cr.fdr)
    return out


@router.post("/{cr_id}/recommend")
def recommend(cr_id: int, body: RecommendIn, user: User = Depends(require_roles(*REVIEWER_ROLES)),
              db: Session = Depends(get_db)):
    cr = _load(db, cr_id, user)
    if cr.status != ClearanceStatus.PENDING_OFFICER_REVIEW:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This request is not awaiting officer review.")
    prev = cr.status
    cr.recommendation = body.recommendation
    cr.recommendation_remarks = body.remarks
    cr.recommended_by_id = user.id
    cr.recommended_at = utcnow()
    cr.status = (ClearanceStatus.RECOMMENDED_APPROVAL if body.recommendation == "approve"
                 else ClearanceStatus.RECOMMENDED_REJECTION)
    audit.record(db, user, "clearance_recommended",
                 f"Officer recommended {'APPROVAL' if body.recommendation == 'approve' else 'REJECTION'}: {body.remarks}",
                 fdr_id=cr.fdr_id, entity_type="clearance_request", entity_id=cr.id,
                 previous_status=prev, new_status=cr.status)
    notify_staff(db, (Role.SENIOR,), cr.fdr_id, link=f"/senior/decisions/{cr.id}", kind="pending_approval",
                 severity="warning", dedupe_key=f"clearance-approval:{cr.id}",
                 title=f"Final decision needed: {cr.fdr.reference_no}",
                 message=f"{user.full_name} recommended {body.recommendation}. A different senior officer must decide.")
    notify_institution(db, cr.fdr.institution_id, cr.fdr_id, kind="clearance_update",
                       title=f"Clearance reviewed by officer: {cr.fdr.reference_no}",
                       message="Your clearance request has been reviewed and forwarded for the final decision.")
    db.commit()
    return clearance_out(cr, include_fdr=True)


@router.post("/{cr_id}/decide")
def decide(cr_id: int, body: DecideIn, user: User = Depends(require_roles(Role.SENIOR)), db: Session = Depends(get_db)):
    cr = _load(db, cr_id, user)
    if cr.status not in (ClearanceStatus.RECOMMENDED_APPROVAL, ClearanceStatus.RECOMMENDED_REJECTION):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This request is not awaiting a final decision.")
    # Two-person rule: the recommender (and requester) can never record the final decision.
    if user.id in (cr.recommended_by_id, cr.requested_by_id):
        audit.record(db, user, "two_person_rule_blocked",
                     "Blocked: the officer who recommended this clearance attempted the final decision",
                     fdr_id=cr.fdr_id, entity_type="clearance_request", entity_id=cr.id)
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Two-person rule: you recommended this request, so a different senior officer must decide.")
    if body.decision == "approved":
        elig = clearance_eligibility(db, cr.fdr)
        # The open request itself is expected here; every other prerequisite must still hold.
        unmet = [c["label"] for c in elig["checks"] if not c["ok"] and c["code"] != "NO_OPEN_REQUEST"]
        if unmet:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                {"message": "Prerequisites are no longer met.", "unmet": unmet})
    prev = cr.status
    cr.status = ClearanceStatus.APPROVED if body.decision == "approved" else ClearanceStatus.REJECTED
    cr.decided_at = utcnow()
    db.add(ApprovalDecision(clearance_request_id=cr.id, decided_by_id=user.id, decision=body.decision,
                            remarks=body.remarks))
    if cr.status == ClearanceStatus.APPROVED:
        cr.fdr.is_cleared = True
    audit.record(db, user, "clearance_decided",
                 f"Final decision (demo): {body.decision.upper()} - {body.remarks.rstrip('.')}. No funds are released by this system.",
                 fdr_id=cr.fdr_id, entity_type="clearance_request", entity_id=cr.id,
                 previous_status=prev, new_status=cr.status)
    notify_institution(db, cr.fdr.institution_id, cr.fdr_id, kind="clearance_decision",
                       severity="success" if cr.status == ClearanceStatus.APPROVED else "critical",
                       title=f"Clearance {body.decision} (demo): {cr.fdr.reference_no}",
                       message=f"{body.remarks[:300]} - Note: actual release of funds happens outside this demo system.")
    if cr.recommended_by_id:
        notify_staff(db, (Role.OFFICER, Role.SENIOR), cr.fdr_id, link=f"/officer/clearances/{cr.id}",
                     kind="clearance_decision", title=f"Clearance {body.decision}: {cr.fdr.reference_no}",
                     message=f"Final decision recorded by {user.full_name}.")
    db.commit()
    db.refresh(cr)
    return clearance_out(cr, include_fdr=True)
