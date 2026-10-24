"""SQLAlchemy models. Every table has timestamps; foreign keys and indexes are declared explicitly."""
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---- Enumerations (kept as plain strings so SQLite and PostgreSQL both handle them simply) ----

class Role:
    INSTITUTION = "institution"
    OFFICER = "officer"
    SENIOR = "senior"
    ADMIN = "admin"
    ALL = (INSTITUTION, OFFICER, SENIOR, ADMIN)


class SubmissionStatus:
    DRAFT = "draft"
    SUBMITTED = "submitted"
    CORRECTION_REQUESTED = "correction_requested"


class DocumentStatus:
    NOT_SUBMITTED = "not_submitted"
    PENDING_REVIEW = "pending_review"
    DISCREPANCY = "discrepancy"
    CORRECTION_REQUESTED = "correction_requested"
    DOCUMENT_CHECKED = "document_checked"
    REJECTED = "rejected"


class BankStatus:
    NOT_STARTED = "not_started"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    MISMATCH = "mismatch"
    FAILED = "failed"


class ClearanceStatus:
    PENDING_OFFICER_REVIEW = "pending_officer_review"
    RECOMMENDED_APPROVAL = "recommended_approval"
    RECOMMENDED_REJECTION = "recommended_rejection"
    APPROVED = "approved"
    REJECTED = "rejected"
    OPEN = (PENDING_OFFICER_REVIEW, RECOMMENDED_APPROVAL, RECOMMENDED_REJECTION)


class DocType:
    FDR_RECEIPT = "fdr_receipt"
    PAYMENT_PROOF = "payment_proof"
    LIEN_LETTER = "lien_letter"
    BANK_EVIDENCE = "bank_evidence"
    OTHER = "other"
    ALL = (FDR_RECEIPT, PAYMENT_PROOF, LIEN_LETTER, BANK_EVIDENCE, OTHER)


# ---- Tables ----

class Institution(Base):
    __tablename__ = "institutions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    city: Mapped[str] = mapped_column(String(80), default="")
    state: Mapped[str] = mapped_column(String(80), default="")
    contact_email: Mapped[str] = mapped_column(String(200), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="institution")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), index=True)
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    institution: Mapped[Institution | None] = relationship(back_populates="users")


class FDRRecord(Base):
    __tablename__ = "fdr_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)

    # Details as entered/confirmed by the institution
    fdr_number: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    bank_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    branch_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    account_holder: Mapped[str | None] = mapped_column(String(200), nullable=True)
    account_number_masked: Mapped[str | None] = mapped_column(String(40), nullable=True)
    principal_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    interest_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    purpose: Mapped[str] = mapped_column(String(120), default="Security Deposit")

    # Separate, evidence-labelled statuses
    submission_status: Mapped[str] = mapped_column(String(30), default=SubmissionStatus.DRAFT, index=True)
    document_status: Mapped[str] = mapped_column(String(30), default=DocumentStatus.NOT_SUBMITTED, index=True)
    bank_status: Mapped[str] = mapped_column(String(30), default=BankStatus.NOT_STARTED, index=True)
    is_cleared: Mapped[bool] = mapped_column(Boolean, default=False)

    assigned_officer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_review_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    institution: Mapped[Institution] = relationship()
    assigned_officer: Mapped[User | None] = relationship(foreign_keys=[assigned_officer_id])
    documents: Mapped[list["UploadedDocument"]] = relationship(back_populates="fdr", order_by="UploadedDocument.id")
    extracted_fields: Mapped[list["ExtractedField"]] = relationship(back_populates="fdr", order_by="ExtractedField.id")
    validation_results: Mapped[list["ValidationResult"]] = relationship(back_populates="fdr", order_by="ValidationResult.id")
    bank_verifications: Mapped[list["BankVerification"]] = relationship(back_populates="fdr", order_by="BankVerification.id")
    clearance_requests: Mapped[list["ClearanceRequest"]] = relationship(back_populates="fdr", order_by="ClearanceRequest.id")


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    fdr_id: Mapped[int] = mapped_column(ForeignKey("fdr_records.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(30))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(80), unique=True)  # random name; never user-controlled
    content_type: Mapped[str] = mapped_column(String(60))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    ocr_status: Mapped[str] = mapped_column(String(20), default="not_run")  # not_run|completed|failed|unavailable
    ocr_engine: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ocr_mean_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    ocr_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    fdr: Mapped[FDRRecord] = relationship(back_populates="documents")
    uploaded_by: Mapped[User] = relationship()


class ExtractedField(Base):
    __tablename__ = "extracted_document_fields"
    __table_args__ = (UniqueConstraint("document_id", "field_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("uploaded_documents.id"), index=True)
    fdr_id: Mapped[int] = mapped_column(ForeignKey("fdr_records.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(40))
    extracted_value: Mapped[str | None] = mapped_column(String(255), nullable=True)  # raw OCR value, never edited
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    needs_review: Mapped[bool] = mapped_column(Boolean, default=True)
    confirmed_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    was_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    fdr: Mapped[FDRRecord] = relationship(back_populates="extracted_fields")


class ValidationResult(Base):
    __tablename__ = "validation_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    fdr_id: Mapped[int] = mapped_column(ForeignKey("fdr_records.id"), index=True)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    check_code: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10))  # error (blocks submission) | warning | info | pass
    field_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    message: Mapped[str] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    fdr: Mapped[FDRRecord] = relationship(back_populates="validation_results")


class BankVerification(Base):
    __tablename__ = "bank_verifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    fdr_id: Mapped[int] = mapped_column(ForeignKey("fdr_records.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(20))  # pending|confirmed|mismatch|failed
    adapter: Mapped[str] = mapped_column(String(40))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    reference: Mapped[str] = mapped_column(String(60))
    remarks: Mapped[str] = mapped_column(Text, default="")
    response_summary: Mapped[str] = mapped_column(Text, default="")
    evidence_document_id: Mapped[int | None] = mapped_column(ForeignKey("uploaded_documents.id"), nullable=True)
    officer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    fdr: Mapped[FDRRecord] = relationship(back_populates="bank_verifications")
    officer: Mapped[User] = relationship()


class ClearanceRequest(Base):
    __tablename__ = "clearance_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    fdr_id: Mapped[int] = mapped_column(ForeignKey("fdr_records.id"), index=True)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default=ClearanceStatus.PENDING_OFFICER_REVIEW, index=True)
    prerequisite_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    recommended_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    recommendation: Mapped[str | None] = mapped_column(String(10), nullable=True)  # approve|reject
    recommendation_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    fdr: Mapped[FDRRecord] = relationship(back_populates="clearance_requests")
    requested_by: Mapped[User] = relationship(foreign_keys=[requested_by_id])
    recommended_by: Mapped[User | None] = relationship(foreign_keys=[recommended_by_id])
    decisions: Mapped[list["ApprovalDecision"]] = relationship(back_populates="clearance_request")


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    clearance_request_id: Mapped[int] = mapped_column(ForeignKey("clearance_requests.id"), index=True)
    decided_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(10))  # approved|rejected
    remarks: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    clearance_request: Mapped[ClearanceRequest] = relationship(back_populates="decisions")
    decided_by: Mapped[User] = relationship()


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "is_read"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    fdr_id: Mapped[int | None] = mapped_column(ForeignKey("fdr_records.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10), default="info")  # info|warning|critical|success
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(String(500))
    link: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PolicyRule(Base):
    __tablename__ = "policy_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    versions: Mapped[list["PolicyVersion"]] = relationship(back_populates="rule", order_by="PolicyVersion.version")


class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    __table_args__ = (UniqueConstraint("rule_id", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("policy_rules.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    value: Mapped[dict] = mapped_column(JSON)
    effective_from: Mapped[date] = mapped_column(Date)
    change_note: Mapped[str] = mapped_column(String(300), default="")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    rule: Mapped[PolicyRule] = relationship(back_populates="versions")
    created_by: Mapped[User | None] = relationship()


class AuditLog(Base):
    """Append-only. Updates/deletes are blocked both here (ORM events) and in SQLite (triggers)."""
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_fdr_time", "fdr_id", "created_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    user_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fdr_id: Mapped[int | None] = mapped_column(ForeignKey("fdr_records.id"), nullable=True)
    previous_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)


@event.listens_for(AuditLog, "before_update")
def _block_audit_update(*_):
    raise PermissionError("Audit log entries are append-only")


@event.listens_for(AuditLog, "before_delete")
def _block_audit_delete(*_):
    raise PermissionError("Audit log entries are append-only")
