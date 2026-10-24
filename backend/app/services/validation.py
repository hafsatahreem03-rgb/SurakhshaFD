"""Automatic validation of an FDR record.

Severity:
  error   - blocks submission (missing/invalid data the institution must fix)
  warning - submission allowed, but flagged for officer review (never an automatic rejection)
  info    - informational
  pass    - check passed
"""
import re
import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import DocType, DocumentStatus, ExtractedField, FDRRecord, UploadedDocument, ValidationResult
from .ocr import FIELD_LABELS, to_python
from .policy import get_policy

REQUIRED_FIELDS = ["fdr_number", "bank_name", "branch_name", "account_holder", "principal_amount", "issue_date", "maturity_date"]

DOC_LABELS = {
    DocType.FDR_RECEIPT: "FDR receipt",
    DocType.PAYMENT_PROOF: "Payment proof",
    DocType.LIEN_LETTER: "Bank lien letter",
    DocType.BANK_EVIDENCE: "Bank evidence",
    DocType.OTHER: "Other document",
}


def norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def inr(v: float) -> str:
    """Format rupees in the Indian grouping style, e.g. 1000000 -> ₹10,00,000."""
    neg, v = v < 0, abs(round(v))
    s = str(int(v))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        s = f"{head},{tail}"
    return ("-₹" if neg else "₹") + s


def latest_ocr_values(db: Session, fdr: FDRRecord) -> dict[str, str]:
    """Raw OCR values from the most recent FDR receipt that was OCR-processed."""
    doc = db.execute(
        select(UploadedDocument)
        .where(UploadedDocument.fdr_id == fdr.id, UploadedDocument.doc_type == DocType.FDR_RECEIPT,
               UploadedDocument.ocr_status == "completed")
        .order_by(UploadedDocument.id.desc()).limit(1)
    ).scalar_one_or_none()
    if doc is None:
        return {}
    rows = db.execute(select(ExtractedField).where(ExtractedField.document_id == doc.id)).scalars()
    return {r.field_name: r.extracted_value for r in rows if r.extracted_value}


def run_validation(db: Session, fdr: FDRRecord, persist: bool = True) -> list[dict]:
    results: list[dict] = []

    def add(code: str, severity: str, message: str, field: str | None = None):
        results.append({"check_code": code, "severity": severity, "message": message, "field_name": field})

    # 1. Missing required fields
    missing = [f for f in REQUIRED_FIELDS if getattr(fdr, f) in (None, "")]
    for f in missing:
        add("MISSING_FIELD", "error", f"{FIELD_LABELS[f]} is required.", f)
    if not missing:
        add("MISSING_FIELD", "pass", "All required fields are filled in.")

    # 2. Duplicate FDR number (same number + same bank anywhere in the system)
    if fdr.fdr_number:
        candidates = db.execute(
            select(FDRRecord).where(FDRRecord.id != fdr.id,
                                    func.lower(FDRRecord.fdr_number) == fdr.fdr_number.lower())
        ).scalars().all()
        dups = [c for c in candidates
                if (not fdr.bank_name or not c.bank_name or norm(c.bank_name) == norm(fdr.bank_name))
                and c.document_status != DocumentStatus.REJECTED]
        if dups:
            refs = ", ".join(d.reference_no for d in dups[:3])
            add("DUPLICATE_FDR", "warning",
                f"Possible duplicate: FDR number {fdr.fdr_number} is already recorded ({refs}). An officer must review this.",
                "fdr_number")
        else:
            add("DUPLICATE_FDR", "pass", "FDR number is not used by any other record.")

    # 3 & 4. Date checks
    today = date.today()
    if fdr.issue_date and fdr.issue_date > today:
        add("INVALID_DATE", "error", "Issue date cannot be in the future.", "issue_date")
    if fdr.issue_date and fdr.issue_date.year < 1990:
        add("INVALID_DATE", "error", "Issue date looks invalid (before 1990).", "issue_date")
    if fdr.issue_date and fdr.maturity_date:
        if fdr.maturity_date <= fdr.issue_date:
            add("MATURITY_BEFORE_ISSUE", "error", "Maturity date must be later than the issue date.", "maturity_date")
        else:
            add("MATURITY_BEFORE_ISSUE", "pass", "Maturity date is after the issue date.")
    if fdr.maturity_date and fdr.maturity_date < today:
        add("ALREADY_MATURED", "warning", f"This FDR matured on {fdr.maturity_date:%d %b %Y}.", "maturity_date")

    # 5. Compare entered values with OCR values
    tol = get_policy(db, "validation_tolerances")
    ocr = latest_ocr_values(db, fdr)
    if ocr:
        ocr_amount = to_python("principal_amount", ocr.get("principal_amount"))
        if ocr_amount is not None and fdr.principal_amount is not None:
            if abs(ocr_amount - fdr.principal_amount) > float(tol.get("amount_tolerance_rupees", 1)):
                add("AMOUNT_MISMATCH", "warning",
                    f"Amount mismatch detected. Entered {inr(fdr.principal_amount)} but the uploaded FDR reads "
                    f"{inr(ocr_amount)}. Please review the uploaded FDR and entered information.",
                    "principal_amount")
            else:
                add("AMOUNT_MISMATCH", "pass", "Entered amount matches the amount read from the document.")
        for f in ("fdr_number", "maturity_date", "issue_date"):
            ov, ev = ocr.get(f), getattr(fdr, f)
            if ov and ev and norm(str(ov)) != norm(ev.isoformat() if isinstance(ev, date) else str(ev)):
                add("OCR_FIELD_MISMATCH", "warning",
                    f"{FIELD_LABELS[f]} entered ({ev}) differs from the document ({ov}). Please double-check.", f)
        ob = ocr.get("bank_name")
        if ob and fdr.bank_name and norm(fdr.bank_name) not in norm(ob) and norm(ob) not in norm(fdr.bank_name):
            add("OCR_FIELD_MISMATCH", "warning",
                f"Bank name entered ({fdr.bank_name}) differs from the document ({ob}).", "bank_name")
    else:
        add("NO_OCR", "info", "No OCR reading is available for comparison. Officer will compare manually.")

    # Account holder should name the institution
    inst_name = fdr.institution.name if fdr.institution else ""
    if fdr.account_holder and inst_name:
        core = norm(re.sub(r"\(demo\)", "", inst_name, flags=re.IGNORECASE))
        if core and core[:12] not in norm(fdr.account_holder):
            add("HOLDER_MISMATCH", "warning",
                f"Account holder '{fdr.account_holder}' does not appear to match the institution '{inst_name}'.",
                "account_holder")

    # 6. Required supporting documents
    req_docs = get_policy(db, "required_documents").get("documents", [])
    present = {d.doc_type for d in fdr.documents}
    missing_docs = [d for d in req_docs if d not in present]
    if missing_docs:
        add("MISSING_DOCUMENT", "error",
            "Missing required document(s): " + ", ".join(DOC_LABELS.get(d, d) for d in missing_docs) + ".")
    else:
        add("MISSING_DOCUMENT", "pass", "All required supporting documents are uploaded.")

    # 7. Configured (demo) deposit requirements
    dep = get_policy(db, "deposit_requirements")
    min_p = dep.get("minimum_principal")
    if min_p and fdr.principal_amount is not None and fdr.principal_amount < float(min_p):
        add("DEPOSIT_REQUIREMENT", "warning",
            f"Principal {inr(fdr.principal_amount)} is below the configured demo minimum of {inr(float(min_p))}.",
            "principal_amount")
    min_days = dep.get("minimum_tenure_days")
    if min_days and fdr.issue_date and fdr.maturity_date and (fdr.maturity_date - fdr.issue_date).days < int(min_days):
        add("DEPOSIT_REQUIREMENT", "warning",
            f"Tenure is {(fdr.maturity_date - fdr.issue_date).days} days; the demo policy expects at least {min_days} days.",
            "maturity_date")

    # 8. Other inconsistencies needing manual review
    if fdr.interest_rate is not None and not (0 < fdr.interest_rate < 15):
        add("REVIEW_NEEDED", "warning", f"Interest rate {fdr.interest_rate}% looks unusual.", "interest_rate")
    unconfirmed = db.execute(
        select(func.count()).select_from(ExtractedField)
        .where(ExtractedField.fdr_id == fdr.id, ExtractedField.needs_review.is_(True),
               ExtractedField.is_confirmed.is_(False))
    ).scalar_one()
    if unconfirmed:
        add("LOW_CONFIDENCE", "info", f"{unconfirmed} OCR value(s) had low confidence and were not explicitly confirmed.")

    if persist:
        run_id = uuid.uuid4().hex[:12]
        for r in results:
            db.add(ValidationResult(fdr_id=fdr.id, run_id=run_id, **r))
        db.flush()
    return results


def latest_results(db: Session, fdr_id: int) -> list[ValidationResult]:
    last = db.execute(
        select(ValidationResult.run_id).where(ValidationResult.fdr_id == fdr_id)
        .order_by(ValidationResult.id.desc()).limit(1)
    ).scalar_one_or_none()
    if not last:
        return []
    return list(db.execute(
        select(ValidationResult).where(ValidationResult.run_id == last).order_by(ValidationResult.id)
    ).scalars())


def summarize(results) -> dict:
    sev = [r["severity"] if isinstance(r, dict) else r.severity for r in results]
    return {"errors": sev.count("error"), "warnings": sev.count("warning"),
            "info": sev.count("info"), "passed": sev.count("pass")}
