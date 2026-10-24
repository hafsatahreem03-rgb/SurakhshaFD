"""In-app notifications (no SMS/email needed)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Notification, Role, User


def users_for_institution(db: Session, institution_id: int) -> list[User]:
    return list(db.execute(select(User).where(User.institution_id == institution_id, User.is_active.is_(True))).scalars())


def users_with_roles(db: Session, *roles: str) -> list[User]:
    return list(db.execute(select(User).where(User.role.in_(roles), User.is_active.is_(True))).scalars())


def notify(db: Session, users, *, kind: str, title: str, message: str, severity: str = "info",
           fdr_id: int | None = None, link: str | None = None, dedupe_key: str | None = None) -> int:
    """Create a notification per user. With dedupe_key, a user never gets the same alert twice."""
    created = 0
    for u in users:
        key = f"{dedupe_key}:u{u.id}" if dedupe_key else None
        if key and db.execute(select(Notification.id).where(Notification.dedupe_key == key)).first():
            continue
        db.add(Notification(user_id=u.id, fdr_id=fdr_id, kind=kind, title=title, message=message,
                            severity=severity, link=link, dedupe_key=key))
        created += 1
    db.flush()
    return created


def fdr_link(user_role: str, fdr_id: int) -> str:
    return f"/institution/fdrs/{fdr_id}" if user_role == Role.INSTITUTION else f"/officer/cases/{fdr_id}"


def notify_institution(db: Session, institution_id: int, fdr_id: int, **kw) -> int:
    return notify(db, users_for_institution(db, institution_id), fdr_id=fdr_id,
                  link=f"/institution/fdrs/{fdr_id}", **kw)


def notify_staff(db: Session, roles: tuple[str, ...], fdr_id: int | None, link: str | None = None, **kw) -> int:
    return notify(db, users_with_roles(db, *roles), fdr_id=fdr_id,
                  link=link or (f"/officer/cases/{fdr_id}" if fdr_id else None), **kw)
