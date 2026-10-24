"""FDR records: create, edit, upload + OCR, validate, submit, officer review, simulated bank verification."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import audit
from ..database import get_db
from ..models import (
    AuditLog, BankVerification, ClearanceRequest, DocType, DocumentStatus, ExtractedField, FDRRecord, Role,
    SubmissionStatus, UploadedDocument, User, utcnow,
)
from ..schemas import (
    BankVerifyIn, ClearanceCreateIn, ConfirmFieldsIn, FDRFieldsIn, ReviewActionIn, audit_out, clearance_out,
    document_out, fdr_summary, field_out, verification_out,
)
from ..security import REVIEWER_ROLES, get_current_user, get_fdr_for_user, require_roles
from ..services import storage
from ..services.bank_adapter import get_adapter
from ..services.notify import notify_institution, notify_staff
from ..services.ocr import run_ocr
from ..services.policy import get_policy
from ..services.validation import latest_results, run_validation, summarize
from ..services.workflow import clearance_eligibility

router = APIRouter(prefix="/api/fdrs", tags=["fdrs"])

EDITABLE = (SubmissionStatus.DRAFT, SubmissionStatus.CORRECTION_REQUESTED)
AUDITED_FIELDS = ["fdr_number", "bank_name", "branch_name", "account_holder", "principal_amount",
                  "interest_rate", "issue_date", "maturity_date", "purpose", "account_number_masked"]


def _bad(msg: str, code: int = status.HTTP_400_BAD_REQUEST):
    raise HTTPException(code, msg)


# ---------------- listing & detail ----------------

@router.get("")
def list_fdrs(
    q: str | None = None,
    stage: str | None = None,
    document_status: str | None = None,
    bank_status: str | None = None,
    institution_id: int | None = None,
    assigned: str | None = Query(None, pattern="^(me|unassigned)$"),
    maturing_within_days: int | None = Query(None, ge=0, le=3650),
    date_from: date | None = None,
    date_to: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(FDRRecord).order_by(FDRRecord.updated_at.desc())
    if user.role == Role.INSTITUTION:
        stmt = stmt.where(FDRRecord.institution_id == user.institution_id)
    elif institution_id:
        stmt = stmt.where(FDRRecord.institution_id == institution_id)
    if user.role != Role.INSTITUTION:  # staff never see other institutions' unsubmitted drafts
        stmt = stmt.where(FDRRecord.submission_status != SubmissionStatus.DRAFT)
    if document_status:
        stmt = stmt.where(FDRRecord.document_status == document_status)
    if bank_status:
        stmt = stmt.where(FDRRecord.bank_status == bank_status)
    if assigned == "me":
        stmt = stmt.where(FDRRecord.assigned_officer_id == user.id)
    elif assigned == "unassigned":
        stmt = stmt.where(FDRRecord.assigned_officer_id.is_(None))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(FDRRecord.reference_no.ilike(like), FDRRecord.fdr_number.ilike(like),
                              FDRRecord.bank_name.ilike(like), FDRRecord.account_holder.ilike(like)))
    if maturing_within_days is not None:
        stmt = stmt.where(FDRRecord.maturity_date <= date.today() + timedelta(days=maturing_within_days),
                          FDRRecord.is_cleared.is_(False))
    if date_from:
        stmt = stmt.where(FDRRecord.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        stmt = stmt.where(FDRRecord.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    rows = db.execute(stmt).scalars().all()
    out = []
    for f in rows:
        s = fdr_summary(f)
        if stage and s["stage"] != stage:
            continue
        v = summarize(latest_results(db, f.id))
        s["validation"] = v
        out.append(s)
    return out


def _receipt_doc(fdr: FDRRecord) -> UploadedDocument | None:
    receipts = [d for d in fdr.documents if d.doc_type == DocType.FDR_RECEIPT]
    return receipts[-1] if receipts else None


@router.get("/{fdr_id}")
def get_fdr(fdr_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fdr = get_fdr_for_user(db, fdr_id, user)
    if user.role != Role.INSTITUTION and fdr.submission_status == SubmissionStatus.DRAFT:
        _bad("FDR record not found.", status.HTTP_404_NOT_FOUND)
    receipt = _receipt_doc(fdr)
    fields = [f for f in fdr.extracted_fields if receipt and f.document_id == receipt.id]
    timeline = db.execute(select(AuditLog).where(AuditLog.fdr_id == fdr.id).order_by(AuditLog.id)).scalars()
    return {
        **fdr_summary(fdr),
        "documents": [document_out(d) for d in fdr.documents],
        "receipt_document_id": receipt.id if receipt else None,
        "ocr_text": receipt.ocr_text if receipt else None,  # access already checked by get_fdr_for_user
        "extracted_fields": [field_out(f) for f in fields],
        "validation_results": [
            {"check_code": r.check_code, "severity": r.severity, "message": r.message,
             "field_name": r.field_name, "created_at": r.created_at.isoformat()}
            for r in latest_results(db, fdr.id)
        ],
        "bank_verifications": [verification_out(v) for v in reversed(fdr.bank_verifications)],
        "clearance_requests": [clearance_out(c) for c in reversed(fdr.clearance_requests)],
        "eligibility": clearance_eligibility(db, fdr),
        "required_documents": get_policy(db, "required_documents").get("documents", []),
        "audit": [audit_out(a) for a in timeline],
    }


# ---------------- institution: create / edit ----------------

def _next_reference(db: Session, fdr: FDRRecord) -> str:
    return f"SFD-{date.today().year}-{fdr.id:04d}"


@router.post("", status_code=201)
def create_fdr(body: FDRFieldsIn, user: User = Depends(require_roles(Role.INSTITUTION)), db: Session = Depends(get_db)):
    fdr = FDRRecord(reference_no=f"TMP-{utcnow().timestamp()}-{user.id}", institution_id=user.institution_id,
                    created_by_id=user.id, **{k: v for k, v in body.model_dump().items() if v is not None})
    db.add(fdr)
    db.flush()
    fdr.reference_no = _next_reference(db, fdr)
    audit.record(db, user, "fdr_created", f"Draft {fdr.reference_no} created", fdr_id=fdr.id,
                 entity_type="fdr", entity_id=fdr.id, new_status=SubmissionStatus.DRAFT)
    db.commit()
    return fdr_summary(fdr)


@router.put("/{fdr_id}")
def update_fdr(fdr_id: int, body: FDRFieldsIn, user: User = Depends(require_roles(Role.INSTITUTION)),
               db: Session = Depends(get_db)):
    fdr = get_fdr_for_user(db, fdr_id, user)
    if fdr.submission_status not in EDITABLE:
        _bad("This FDR has been submitted and can no longer be edited unless an officer requests a correction.")
    data = body.model_dump(exclude_unset=True)
    changes = {}
    for k, v in data.items():
        old = getattr(fdr, k)
        if old != v:
            changes[k] = {"from": str(old) if old is not None else None, "to": str(v) if v is not None else None}
            setattr(fdr, k, v)
    if changes:
        audit.record(db, user, "fdr_details_updated", f"Updated: {', '.join(changes)}", fdr_id=fdr.id,
                     entity_type="fdr", entity_id=fdr.id,
                     details={"changes": {k: v for k, v in changes.items() if k in AUDITED_FIELDS}})
    db.commit()
    return fdr_summary(fdr)


# ---------------- documents + OCR ----------------

@router.post("/{fdr_id}/documents", status_code=201)
async def upload_document(
    fdr_id: int,
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if doc_type not in DocType.ALL:
        _bad("Unknown document type.")
    fdr = get_fdr_for_user(db, fdr_id, user)
    if user.role == Role.INSTITUTION:
        if fdr.submission_status not in EDITABLE:
            _bad("Documents can only be added while the FDR is a draft or a correction was requested.")
        if doc_type == DocType.BANK_EVIDENCE:
            _bad("Bank evidence is uploaded by AICTE officers.")
    elif user.role in REVIEWER_ROLES:
        if doc_type != DocType.BANK_EVIDENCE:
            _bad("Officers may only attach bank verification evidence.")
    else:
        _bad("Your role cannot upload documents.", status.HTTP_403_FORBIDDEN)

    meta = await storage.save_upload(file)
    doc = UploadedDocument(fdr_id=fdr.id, doc_type=doc_type, uploaded_by_id=user.id, **meta)
    db.add(doc)
    db.flush()
    audit.record(db, user, "document_uploaded", f"Uploaded {doc_type.replace('_', ' ')}: {meta['original_filename']}",
                 fdr_id=fdr.id, entity_type="document", entity_id=doc.id,
                 details={"doc_type": doc_type, "size_bytes": meta["size_bytes"], "sha256": meta["sha256"]})

    fields_out = []
    if doc_type == DocType.FDR_RECEIPT:
        data = storage.resolve_stored(doc.stored_filename).read_bytes()
        low = float(get_policy(db, "validation_tolerances").get("low_confidence_threshold", 70))
        result = await run_in_threadpool(run_ocr, data, doc.content_type, low)
        doc.ocr_status, doc.ocr_engine, doc.ocr_message = result.status, result.engine, result.message
        doc.ocr_mean_confidence, doc.ocr_text, doc.ocr_duration_ms = result.mean_confidence, result.text, result.duration_ms
        for ev in result.fields:
            ef = ExtractedField(document_id=doc.id, fdr_id=fdr.id, field_name=ev.field_name,
                                extracted_value=ev.value, confidence=ev.confidence, needs_review=ev.needs_review)
            db.add(ef)
        db.flush()
        found = [ev.field_name for ev in result.fields if ev.value]
        audit.record(db, user, "ocr_completed" if result.status == "completed" else "ocr_" + result.status,
                     result.message, fdr_id=fdr.id, entity_type="document", entity_id=doc.id,
                     details={"engine": result.engine, "fields_found": found,
                              "needs_review": [ev.field_name for ev in result.fields if ev.needs_review],
                              "mean_confidence": result.mean_confidence, "duration_ms": result.duration_ms})
        fields_out = [field_out(f) for f in db.execute(
            select(ExtractedField).where(ExtractedField.document_id == doc.id).order_by(ExtractedField.id)).scalars()]
    db.commit()
    return {"document": document_out(doc), "extracted_fields": fields_out}


@router.put("/{fdr_id}/extracted-fields")
def confirm_extracted_fields(fdr_id: int, body: ConfirmFieldsIn,
                             user: User = Depends(require_roles(Role.INSTITUTION)), db: Session = Depends(get_db)):
    """The institution reviews OCR output; raw OCR values are preserved, confirmed values stored alongside."""
    fdr = get_fdr_for_user(db, fdr_id, user)
    if fdr.submission_status not in EDITABLE:
        _bad("This FDR is no longer editable.")
    corrected = []
    for upd in body.fields:
        ef = db.get(ExtractedField, upd.id)
        if ef is None or ef.fdr_id != fdr.id:
            _bad("Invalid extracted field.")
        val = (upd.confirmed_value or "").strip() or None
        ef.confirmed_value = val
        ef.is_confirmed = True
        ef.was_corrected = (val or "") != (ef.extracted_value or "")
        if ef.was_corrected:
            corrected.append(ef.field_name)
    audit.record(db, user, "ocr_reviewed",
                 f"OCR results reviewed; {len(corrected)} value(s) corrected" if corrected else "OCR results reviewed and confirmed",
                 fdr_id=fdr.id, entity_type="fdr", entity_id=fdr.id, details={"corrected_fields": corrected})
    db.commit()
    return {"ok": True, "corrected_fields": corrected}


# ---------------- validation & submission ----------------

@router.post("/{fdr_id}/validate")
def validate_fdr(fdr_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fdr = get_fdr_for_user(db, fdr_id, user)
    results = run_validation(db, fdr)
    s = summarize(results)
    audit.record(db, user, "validation_run", f"Validation: {s['errors']} error(s), {s['warnings']} warning(s)",
                 fdr_id=fdr.id, entity_type="fdr", entity_id=fdr.id,
                 details={**s, "issues": [r["check_code"] for r in results if r["severity"] in ("error", "warning")]})
    db.commit()
    return {"summary": s, "results": results}


@router.post("/{fdr_id}/submit")
def submit_fdr(fdr_id: int, user: User = Depends(require_roles(Role.INSTITUTION)), db: Session = Depends(get_db)):
    fdr = get_fdr_for_user(db, fdr_id, user)
    if fdr.submission_status not in EDITABLE:
        _bad("This FDR has already been submitted.")
    results = run_validation(db, fdr)
    s = summarize(results)
    if s["errors"]:
        audit.record(db, user, "submission_blocked", f"Submission blocked by {s['errors']} validation error(s)",
                     fdr_id=fdr.id, entity_type="fdr", entity_id=fdr.id,
                     details={"issues": [r["check_code"] for r in results if r["severity"] == "error"]})
        db.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            {"message": "Please fix the errors before submitting.", "summary": s, "results": results})
    prev_sub, prev_doc = fdr.submission_status, fdr.document_status
    resubmission = prev_sub == SubmissionStatus.CORRECTION_REQUESTED
    sla = int(get_policy(db, "alert_intervals").get("review_sla_days", 7))
    fdr.submission_status = SubmissionStatus.SUBMITTED
    fdr.document_status = DocumentStatus.PENDING_REVIEW
    fdr.submitted_at = utcnow()
    fdr.review_due_at = utcnow() + timedelta(days=sla)
    audit.record(db, user, "fdr_resubmitted" if resubmission else "fdr_submitted",
                 f"{fdr.reference_no} {'re' if resubmission else ''}submitted with {s['warnings']} warning(s) for officer review",
                 fdr_id=fdr.id, entity_type="fdr", entity_id=fdr.id,
                 previous_status=f"{prev_sub}/{prev_doc}", new_status=f"{fdr.submission_status}/{fdr.document_status}",
                 details=s)
    notify_staff(db, (Role.OFFICER,), fdr.id, kind="new_submission",
                 severity="warning" if s["warnings"] else "info",
                 title=f"{'Resubmitted' if resubmission else 'New'} FDR for review: {fdr.reference_no}",
                 message=f"{fdr.institution.name} submitted FDR {fdr.fdr_number}"
                         + (f" with {s['warnings']} validation warning(s)." if s["warnings"] else "."))
    db.commit()
    return {"fdr": fdr_summary(fdr), "summary": s, "results": results}


# ---------------- officer review ----------------

REVIEW_TRANSITIONS = {
    "mark_checked": DocumentStatus.DOCUMENT_CHECKED,
    "mark_discrepancy": DocumentStatus.DISCREPANCY,
    "request_correction": DocumentStatus.CORRECTION_REQUESTED,
    "reject": DocumentStatus.REJECTED,
    "reopen": DocumentStatus.PENDING_REVIEW,
}


@router.post("/{fdr_id}/review")
def review_fdr(fdr_id: int, body: ReviewActionIn, user: User = Depends(require_roles(*REVIEWER_ROLES)),
               db: Session = Depends(get_db)):
    fdr = get_fdr_for_user(db, fdr_id, user)
    if fdr.submission_status != SubmissionStatus.SUBMITTED:
        _bad("Only submitted FDRs can be reviewed.")
    if fdr.is_cleared:
        _bad("This FDR has already been cleared.")
    active = (DocumentStatus.PENDING_REVIEW, DocumentStatus.DISCREPANCY)
    if body.action == "reopen":
        if fdr.document_status not in (DocumentStatus.DOCUMENT_CHECKED, DocumentStatus.REJECTED):
            _bad("Only checked or rejected documents can be reopened.")
    elif fdr.document_status not in active:
        _bad(f"Document review is not open (current status: {fdr.document_status.replace('_', ' ')}).")

    prev = fdr.document_status
    fdr.document_status = REVIEW_TRANSITIONS[body.action]
    fdr.last_review_remarks = body.remarks
    if fdr.assigned_officer_id is None:
        fdr.assigned_officer_id = user.id
    if body.action == "request_correction":
        fdr.submission_status = SubmissionStatus.CORRECTION_REQUESTED
    labels = {"mark_checked": "Documents checked", "mark_discrepancy": "Discrepancy marked",
              "request_correction": "Correction requested", "reject": "FDR document rejected",
              "reopen": "Review reopened"}
    audit.record(db, user, f"review_{body.action}", f"{labels[body.action]}: {body.remarks}", fdr_id=fdr.id,
                 entity_type="fdr", entity_id=fdr.id, previous_status=prev, new_status=fdr.document_status)
    sev = {"mark_checked": "success", "reject": "critical"}.get(body.action, "warning")
    notify_institution(db, fdr.institution_id, fdr.id, kind="review_update", severity=sev,
                       title=f"{labels[body.action]}: {fdr.reference_no}", message=body.remarks[:400])
    db.commit()
    return fdr_summary(fdr)


@router.post("/{fdr_id}/assign")
def assign_to_me(fdr_id: int, user: User = Depends(require_roles(*REVIEWER_ROLES)), db: Session = Depends(get_db)):
    fdr = get_fdr_for_user(db, fdr_id, user)
    prev = fdr.assigned_officer.full_name if fdr.assigned_officer else None
    fdr.assigned_officer_id = user.id
    audit.record(db, user, "case_assigned", f"Case assigned to {user.full_name}", fdr_id=fdr.id,
                 entity_type="fdr", entity_id=fdr.id, previous_status=prev, new_status=user.full_name)
    db.commit()
    return fdr_summary(fdr)


# ---------------- simulated bank verification ----------------

@router.post("/{fdr_id}/bank-verifications", status_code=201)
def simulate_bank_verification(fdr_id: int, body: BankVerifyIn, user: User = Depends(require_roles(*REVIEWER_ROLES)),
                               db: Session = Depends(get_db)):
    fdr = get_fdr_for_user(db, fdr_id, user)
    if fdr.submission_status == SubmissionStatus.DRAFT:
        _bad("The FDR has not been submitted yet.")
    if fdr.is_cleared:
        _bad("This FDR has already been cleared.")
    if body.evidence_document_id is not None:
        ev = db.get(UploadedDocument, body.evidence_document_id)
        if ev is None or ev.fdr_id != fdr.id:
            _bad("Evidence document does not belong to this FDR.")
    adapter = get_adapter()
    result = adapter.verify(fdr, body.outcome)
    v = BankVerification(fdr_id=fdr.id, outcome=result.outcome, adapter=result.adapter,
                         is_simulated=result.is_simulated, reference=result.reference, remarks=body.remarks,
                         response_summary=result.summary, evidence_document_id=body.evidence_document_id,
                         officer_id=user.id)
    db.add(v)
    prev = fdr.bank_status
    fdr.bank_status = result.outcome
    db.flush()
    audit.record(db, user, "bank_verification_simulated",
                 f"[DEMO / SIMULATED] Bank verification outcome: {result.outcome} (ref {result.reference})",
                 fdr_id=fdr.id, entity_type="bank_verification", entity_id=v.id, previous_status=prev,
                 new_status=fdr.bank_status, details={"adapter": result.adapter, "simulated": True,
                                                      "reference": result.reference})
    notify_institution(db, fdr.institution_id, fdr.id, kind="bank_verification",
                       severity={"confirmed": "success", "mismatch": "critical", "failed": "critical"}.get(result.outcome, "info"),
                       title=f"[Demo] Bank verification {result.outcome}: {fdr.reference_no}",
                       message=result.summary)
    db.commit()
    return verification_out(v)


# ---------------- clearance request (institution) ----------------

@router.get("/{fdr_id}/clearance-eligibility")
def eligibility(fdr_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return clearance_eligibility(db, get_fdr_for_user(db, fdr_id, user))


@router.post("/{fdr_id}/clearance-requests", status_code=201)
def request_clearance(fdr_id: int, body: ClearanceCreateIn, user: User = Depends(require_roles(Role.INSTITUTION)),
                      db: Session = Depends(get_db)):
    fdr = get_fdr_for_user(db, fdr_id, user)
    elig = clearance_eligibility(db, fdr)
    if not elig["eligible"]:
        failed = [c["label"] for c in elig["checks"] if not c["ok"]]
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            {"message": "Clearance cannot be requested yet.", "unmet": failed})
    cr = ClearanceRequest(fdr_id=fdr.id, requested_by_id=user.id, reason=body.reason, prerequisite_snapshot=elig)
    db.add(cr)
    db.flush()
    audit.record(db, user, "clearance_requested", f"Clearance requested: {body.reason[:200]}", fdr_id=fdr.id,
                 entity_type="clearance_request", entity_id=cr.id, new_status=cr.status)
    notify_staff(db, (Role.OFFICER,), fdr.id, link=f"/officer/clearances/{cr.id}", kind="pending_clearance",
                 dedupe_key=f"clearance-pending:{cr.id}", title=f"Clearance request: {fdr.reference_no}",
                 message=f"{fdr.institution.name} requested clearance of FDR {fdr.fdr_number}.")
    db.commit()
    db.refresh(fdr)
    return clearance_out(cr)


@router.get("/{fdr_id}/audit")
def fdr_audit(fdr_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fdr = get_fdr_for_user(db, fdr_id, user)
    rows = db.execute(select(AuditLog).where(AuditLog.fdr_id == fdr.id).order_by(AuditLog.id)).scalars()
    return [audit_out(a) for a in rows]
