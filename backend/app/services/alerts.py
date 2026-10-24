"""Deadline monitoring job.

Creates de-duplicated in-app alerts for:
  - FDRs maturing within 60 / 30 / 7 days (intervals come from the alert policy)
  - FDRs that have already matured
  - Officer reviews past their review deadline
  - Missing supporting documents
  - Pending clearance requests

Run it any time with:  python -m app.cli run-alerts   (or the "Run alert check" button for admins)
"""
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ClearanceRequest, ClearanceStatus, DocumentStatus, FDRRecord, Role, SubmissionStatus, utcnow
from .notify import notify_institution, notify_staff
from .policy import get_policy
from .validation import DOC_LABELS


def maturity_bucket(days_left: int, intervals: list[int]) -> int | None:
    """Smallest configured interval that days_left falls within, e.g. 25 days -> 30."""
    for d in sorted(intervals):
        if 0 <= days_left <= d:
            return d
    return None


def run_alerts(db: Session, today: date | None = None) -> dict:
    today = today or date.today()
    pol = get_policy(db, "alert_intervals")
    intervals = [int(x) for x in pol.get("days_before_maturity", [60, 30, 7])]
    req_docs = get_policy(db, "required_documents").get("documents", [])
    counts = {"maturity": 0, "matured": 0, "overdue_review": 0, "missing_documents": 0, "pending_clearance": 0}

    fdrs = db.execute(select(FDRRecord).where(FDRRecord.is_cleared.is_(False))).scalars().all()
    for f in fdrs:
        if f.submission_status == SubmissionStatus.DRAFT or f.document_status == DocumentStatus.REJECTED:
            continue
        if f.maturity_date:
            days_left = (f.maturity_date - today).days
            bucket = maturity_bucket(days_left, intervals)
            if bucket is not None:
                sev = "critical" if bucket <= 7 else "warning"
                kw = dict(kind="maturity_alert", severity=sev, dedupe_key=f"maturity:{f.id}:{f.maturity_date}:{bucket}",
                          title=f"{bucket}-day maturity alert: {f.reference_no}",
                          message=f"FDR {f.fdr_number} ({f.bank_name}) matures on {f.maturity_date:%d %b %Y} "
                                  f"- {days_left} day(s) left.")
                counts["maturity"] += notify_institution(db, f.institution_id, f.id, **kw)
                counts["maturity"] += notify_staff(db, (Role.OFFICER,), f.id, **kw)
            elif days_left < 0:
                kw = dict(kind="matured", severity="critical", dedupe_key=f"matured:{f.id}:{f.maturity_date}",
                          title=f"FDR matured: {f.reference_no}",
                          message=f"FDR {f.fdr_number} matured on {f.maturity_date:%d %b %Y}. "
                                  f"Renewal or clearance action may be required.")
                counts["matured"] += notify_institution(db, f.institution_id, f.id, **kw)
                counts["matured"] += notify_staff(db, (Role.OFFICER,), f.id, **kw)

        if (f.document_status in (DocumentStatus.PENDING_REVIEW, DocumentStatus.DISCREPANCY)
                and f.review_due_at and f.review_due_at < utcnow()):
            counts["overdue_review"] += notify_staff(
                db, (Role.OFFICER,), f.id, kind="overdue_review", severity="warning",
                dedupe_key=f"overdue:{f.id}:{f.review_due_at:%Y%m%d}",
                title=f"Review overdue: {f.reference_no}",
                message=f"Document review for {f.institution.name} was due on {f.review_due_at:%d %b %Y}.")

        present = {d.doc_type for d in f.documents}
        missing = [d for d in req_docs if d not in present]
        if missing:
            counts["missing_documents"] += notify_institution(
                db, f.institution_id, f.id, kind="missing_documents", severity="warning",
                dedupe_key=f"missingdocs:{f.id}:{'-'.join(missing)}",
                title=f"Documents missing: {f.reference_no}",
                message="Please upload: " + ", ".join(DOC_LABELS.get(m, m) for m in missing) + ".")

    for cr in db.execute(select(ClearanceRequest).where(ClearanceRequest.status.in_(ClearanceStatus.OPEN))).scalars():
        if cr.status == ClearanceStatus.PENDING_OFFICER_REVIEW:
            counts["pending_clearance"] += notify_staff(
                db, (Role.OFFICER,), cr.fdr_id, link=f"/officer/clearances/{cr.id}", kind="pending_clearance",
                dedupe_key=f"clearance-pending:{cr.id}", title=f"Clearance request awaiting review: {cr.fdr.reference_no}",
                message=f"{cr.fdr.institution.name} requested clearance on {cr.created_at:%d %b %Y}.")
        else:
            counts["pending_clearance"] += notify_staff(
                db, (Role.SENIOR,), cr.fdr_id, link=f"/senior/decisions/{cr.id}", kind="pending_approval",
                dedupe_key=f"clearance-approval:{cr.id}", title=f"Final decision needed: {cr.fdr.reference_no}",
                message=f"Officer recommended {'approval' if cr.recommendation == 'approve' else 'rejection'}. "
                        f"Awaiting senior decision.")
    db.commit()
    counts["ran_at"] = datetime.now().isoformat(timespec="seconds")
    return counts
