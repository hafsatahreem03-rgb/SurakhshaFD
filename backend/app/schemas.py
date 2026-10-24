"""Pydantic request bodies (input validation) and response serializers."""
from datetime import date

from pydantic import BaseModel, Field, field_validator

from .models import (
    AuditLog, BankVerification, ClearanceRequest, ExtractedField, FDRRecord, Notification, UploadedDocument, User,
)
from .services.ocr import FIELD_LABELS
from .services.workflow import days_to_maturity, overall_stage

# ---------------- Requests ----------------


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class FDRFieldsIn(BaseModel):
    fdr_number: str | None = Field(None, max_length=60)
    bank_name: str | None = Field(None, max_length=150)
    branch_name: str | None = Field(None, max_length=150)
    account_holder: str | None = Field(None, max_length=200)
    account_number_masked: str | None = Field(None, max_length=40)
    principal_amount: float | None = Field(None, ge=0, le=1e11)
    interest_rate: float | None = Field(None, ge=0, le=100)
    issue_date: date | None = None
    maturity_date: date | None = None
    purpose: str | None = Field(None, max_length=120)

    @field_validator("fdr_number", "bank_name", "branch_name", "account_holder", "account_number_masked", "purpose")
    @classmethod
    def strip(cls, v):
        if v is None:
            return v
        v = v.strip()
        return v or None

    @field_validator("account_number_masked")
    @classmethod
    def mask(cls, v):
        """Never store a full account number: keep only the last 4 digits."""
        if not v:
            return v
        digits = "".join(c for c in v if c.isdigit())
        return f"XXXXXX{digits[-4:]}" if len(digits) >= 4 else v


class ExtractedFieldUpdate(BaseModel):
    id: int
    confirmed_value: str | None = Field(None, max_length=255)


class ConfirmFieldsIn(BaseModel):
    fields: list[ExtractedFieldUpdate]


class ReviewActionIn(BaseModel):
    action: str = Field(pattern="^(mark_discrepancy|request_correction|mark_checked|reject|reopen)$")
    remarks: str = Field(min_length=3, max_length=2000)


class BankVerifyIn(BaseModel):
    outcome: str = Field(pattern="^(confirmed|mismatch|pending|failed)$")
    remarks: str = Field(min_length=3, max_length=2000)
    evidence_document_id: int | None = None


class ClearanceCreateIn(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


class RecommendIn(BaseModel):
    recommendation: str = Field(pattern="^(approve|reject)$")
    remarks: str = Field(min_length=5, max_length=2000)


class DecideIn(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    remarks: str = Field(min_length=10, max_length=2000, description="Mandatory decision remarks")


class UserCreateIn(BaseModel):
    email: str = Field(min_length=5, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(pattern="^(institution|officer|senior|admin)$")
    institution_id: int | None = None


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=120)
    is_active: bool | None = None
    password: str | None = Field(None, min_length=8, max_length=128)


class InstitutionIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    code: str = Field(min_length=3, max_length=40)
    city: str = Field("", max_length=80)
    state: str = Field("", max_length=80)
    contact_email: str = Field("", max_length=200)


class PolicyVersionIn(BaseModel):
    value: dict
    effective_from: date
    change_note: str = Field(min_length=3, max_length=300)


class PolicyCreateIn(BaseModel):
    key: str = Field(pattern="^[a-z][a-z0-9_]{2,59}$")
    name: str = Field(min_length=3, max_length=120)
    category: str = Field(min_length=2, max_length=40)
    description: str = Field("", max_length=2000)
    value: dict
    effective_from: date
    change_note: str = Field("Created", max_length=300)


# ---------------- Responses ----------------

def user_out(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role,
        "institution_id": u.institution_id,
        "institution_name": u.institution.name if u.institution else None,
        "is_active": u.is_active,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "created_at": u.created_at.isoformat(),
    }


def document_out(d: UploadedDocument) -> dict:
    return {
        "id": d.id, "doc_type": d.doc_type, "original_filename": d.original_filename,
        "content_type": d.content_type, "size_bytes": d.size_bytes, "sha256": d.sha256,
        "uploaded_by": d.uploaded_by.full_name if d.uploaded_by else None,
        "uploaded_at": d.uploaded_at.isoformat(),
        "ocr_status": d.ocr_status, "ocr_engine": d.ocr_engine, "ocr_mean_confidence": d.ocr_mean_confidence,
        "ocr_message": d.ocr_message, "ocr_duration_ms": d.ocr_duration_ms,
    }


def field_out(f: ExtractedField) -> dict:
    return {
        "id": f.id, "document_id": f.document_id, "field_name": f.field_name,
        "label": FIELD_LABELS.get(f.field_name, f.field_name),
        "extracted_value": f.extracted_value, "confidence": f.confidence, "needs_review": f.needs_review,
        "confirmed_value": f.confirmed_value, "is_confirmed": f.is_confirmed, "was_corrected": f.was_corrected,
    }


def verification_out(v: BankVerification) -> dict:
    return {
        "id": v.id, "outcome": v.outcome, "adapter": v.adapter, "is_simulated": v.is_simulated,
        "reference": v.reference, "remarks": v.remarks, "response_summary": v.response_summary,
        "evidence_document_id": v.evidence_document_id,
        "officer": v.officer.full_name if v.officer else None, "created_at": v.created_at.isoformat(),
    }


def clearance_out(c: ClearanceRequest, include_fdr: bool = False) -> dict:
    out = {
        "id": c.id, "fdr_id": c.fdr_id, "status": c.status, "reason": c.reason,
        "requested_by": c.requested_by.full_name if c.requested_by else None,
        "created_at": c.created_at.isoformat(),
        "prerequisite_snapshot": c.prerequisite_snapshot,
        "recommendation": c.recommendation, "recommendation_remarks": c.recommendation_remarks,
        "recommended_by": c.recommended_by.full_name if c.recommended_by else None,
        "recommended_by_id": c.recommended_by_id,
        "recommended_at": c.recommended_at.isoformat() if c.recommended_at else None,
        "decided_at": c.decided_at.isoformat() if c.decided_at else None,
        "decisions": [{
            "id": d.id, "decision": d.decision, "remarks": d.remarks,
            "decided_by": d.decided_by.full_name if d.decided_by else None,
            "decided_by_id": d.decided_by_id, "created_at": d.created_at.isoformat(),
        } for d in c.decisions],
    }
    if include_fdr:
        out["fdr"] = fdr_summary(c.fdr)
    return out


def fdr_summary(f: FDRRecord) -> dict:
    return {
        "id": f.id, "reference_no": f.reference_no,
        "institution_id": f.institution_id, "institution_name": f.institution.name if f.institution else None,
        "fdr_number": f.fdr_number, "bank_name": f.bank_name, "branch_name": f.branch_name,
        "account_holder": f.account_holder, "account_number_masked": f.account_number_masked,
        "principal_amount": f.principal_amount, "interest_rate": f.interest_rate,
        "issue_date": f.issue_date.isoformat() if f.issue_date else None,
        "maturity_date": f.maturity_date.isoformat() if f.maturity_date else None,
        "days_to_maturity": days_to_maturity(f),
        "purpose": f.purpose,
        "submission_status": f.submission_status, "document_status": f.document_status,
        "bank_status": f.bank_status, "is_cleared": f.is_cleared, "stage": overall_stage(f),
        "clearance_status": f.clearance_requests[-1].status if f.clearance_requests else None,
        "assigned_officer": f.assigned_officer.full_name if f.assigned_officer else None,
        "assigned_officer_id": f.assigned_officer_id,
        "submitted_at": f.submitted_at.isoformat() if f.submitted_at else None,
        "review_due_at": f.review_due_at.isoformat() if f.review_due_at else None,
        "last_review_remarks": f.last_review_remarks,
        "created_at": f.created_at.isoformat(), "updated_at": f.updated_at.isoformat(),
    }


def audit_out(a: AuditLog) -> dict:
    return {
        "id": a.id, "created_at": a.created_at.isoformat(), "user_id": a.user_id, "user_email": a.user_email,
        "role": a.role, "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
        "fdr_id": a.fdr_id, "previous_status": a.previous_status, "new_status": a.new_status,
        "description": a.description, "details": a.details,
    }


def notification_out(n: Notification) -> dict:
    return {
        "id": n.id, "kind": n.kind, "severity": n.severity, "title": n.title, "message": n.message,
        "link": n.link, "fdr_id": n.fdr_id, "is_read": n.is_read, "created_at": n.created_at.isoformat(),
    }
