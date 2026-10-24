"""Helper for writing append-only audit records."""
from sqlalchemy.orm import Session

from .models import AuditLog, User


def record(
    db: Session,
    user: User | None,
    action: str,
    description: str = "",
    *,
    fdr_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    previous_status: str | None = None,
    new_status: str | None = None,
    details: dict | None = None,
    email: str | None = None,
) -> AuditLog:
    """Add an audit entry to the session. The caller commits together with the change it describes.

    Never put document text or passwords in `details`.
    """
    entry = AuditLog(
        user_id=user.id if user else None,
        user_email=user.email if user else email,
        role=user.role if user else None,
        action=action,
        description=description[:500],
        fdr_id=fdr_id,
        entity_type=entity_type,
        entity_id=entity_id,
        previous_status=previous_status,
        new_status=new_status,
        details=details or {},
    )
    db.add(entry)
    return entry
