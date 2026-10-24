"""Versioned policy engine.

All values here are FICTIONAL DEMONSTRATION VALUES. They are not AICTE rules and carry no legal meaning.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import PolicyRule, PolicyVersion

DEMO_LABEL = "Fictional demonstration value - not an official AICTE requirement."

# key -> (name, category, description, default value)
DEFAULT_POLICIES: dict[str, tuple[str, str, str, dict]] = {
    "deposit_requirements": (
        "Deposit requirements (demo)",
        "deposit",
        "Minimum principal and tenure an FDR should meet. " + DEMO_LABEL,
        {"minimum_principal": 500000, "minimum_tenure_days": 365},
    ),
    "required_documents": (
        "Required supporting documents (demo)",
        "documents",
        "Documents that must be uploaded with each FDR before submission is complete. " + DEMO_LABEL,
        {"documents": ["fdr_receipt", "payment_proof"]},
    ),
    "alert_intervals": (
        "Alert intervals (demo)",
        "alerts",
        "Days before maturity at which reminders are raised, and the officer review deadline. " + DEMO_LABEL,
        {"days_before_maturity": [60, 30, 7], "review_sla_days": 7},
    ),
    "clearance_prerequisites": (
        "Clearance prerequisites (demo)",
        "clearance",
        "Conditions that must hold before an institution can request clearance. " + DEMO_LABEL,
        {"require_document_checked": True, "require_bank_confirmed": True, "require_no_open_request": True},
    ),
    "validation_tolerances": (
        "Validation tolerances (demo)",
        "validation",
        "How much the entered principal may differ from the OCR value before a mismatch is flagged. " + DEMO_LABEL,
        {"amount_tolerance_rupees": 1, "low_confidence_threshold": 70},
    ),
}


def get_policy(db: Session, key: str, on: date | None = None) -> dict:
    """Return the value of the latest version effective on `on` (default today); falls back to defaults."""
    on = on or date.today()
    row = db.execute(
        select(PolicyVersion)
        .join(PolicyRule)
        .where(PolicyRule.key == key, PolicyVersion.effective_from <= on)
        .order_by(PolicyVersion.effective_from.desc(), PolicyVersion.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is not None:
        return row.value
    return dict(DEFAULT_POLICIES[key][3]) if key in DEFAULT_POLICIES else {}


def ensure_default_policies(db: Session, effective_from: date, created_by_id: int | None = None) -> None:
    for key, (name, category, description, value) in DEFAULT_POLICIES.items():
        rule = db.execute(select(PolicyRule).where(PolicyRule.key == key)).scalar_one_or_none()
        if rule is None:
            rule = PolicyRule(key=key, name=name, category=category, description=description)
            db.add(rule)
            db.flush()
            db.add(PolicyVersion(
                rule_id=rule.id, version=1, value=value, effective_from=effective_from,
                change_note="Initial demo policy", created_by_id=created_by_id,
            ))
    db.flush()
