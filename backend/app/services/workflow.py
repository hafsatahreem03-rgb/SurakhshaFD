"""Workflow helpers: overall stage label and clearance eligibility."""
from datetime import date

from ..models import BankStatus, ClearanceStatus, DocumentStatus, FDRRecord, SubmissionStatus
from .policy import get_policy


def current_clearance(fdr: FDRRecord):
    return fdr.clearance_requests[-1] if fdr.clearance_requests else None


def overall_stage(fdr: FDRRecord) -> str:
    """One human-friendly stage for tables. The separate statuses remain the source of truth."""
    cr = current_clearance(fdr)
    if fdr.is_cleared:
        return "cleared_demo"
    if cr and cr.status == ClearanceStatus.PENDING_OFFICER_REVIEW:
        return "clearance_requested"
    if cr and cr.status in (ClearanceStatus.RECOMMENDED_APPROVAL, ClearanceStatus.RECOMMENDED_REJECTION):
        return "awaiting_final_approval"
    if fdr.submission_status == SubmissionStatus.DRAFT:
        return "draft"
    if fdr.document_status == DocumentStatus.REJECTED:
        return "rejected"
    if fdr.submission_status == SubmissionStatus.CORRECTION_REQUESTED:
        return "correction_requested"
    if fdr.document_status in (DocumentStatus.PENDING_REVIEW, DocumentStatus.DISCREPANCY):
        return "under_document_review"
    if fdr.document_status == DocumentStatus.DOCUMENT_CHECKED:
        if fdr.bank_status == BankStatus.CONFIRMED:
            return "bank_confirmed_demo"
        return "awaiting_bank_verification"
    return "submitted"


def days_to_maturity(fdr: FDRRecord, today: date | None = None) -> int | None:
    if not fdr.maturity_date:
        return None
    return (fdr.maturity_date - (today or date.today())).days


def clearance_eligibility(db, fdr: FDRRecord) -> dict:
    pol = get_policy(db, "clearance_prerequisites")
    checks = [{"code": "SUBMITTED", "label": "FDR has been submitted",
               "ok": fdr.submission_status == SubmissionStatus.SUBMITTED}]
    if pol.get("require_document_checked", True):
        checks.append({"code": "DOCUMENT_CHECKED", "label": "Documents checked by an AICTE officer",
                       "ok": fdr.document_status == DocumentStatus.DOCUMENT_CHECKED})
    if pol.get("require_bank_confirmed", True):
        checks.append({"code": "BANK_CONFIRMED", "label": "Bank verification confirmed (simulated in demo)",
                       "ok": fdr.bank_status == BankStatus.CONFIRMED})
    if pol.get("require_no_open_request", True):
        cr = current_clearance(fdr)
        checks.append({"code": "NO_OPEN_REQUEST", "label": "No clearance request already in progress",
                       "ok": not (cr and cr.status in ClearanceStatus.OPEN)})
    checks.append({"code": "NOT_CLEARED", "label": "FDR has not already been cleared", "ok": not fdr.is_cleared})
    return {"eligible": all(c["ok"] for c in checks), "checks": checks}
