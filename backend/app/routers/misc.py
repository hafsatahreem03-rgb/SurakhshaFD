"""Documents download, notifications, health check and sample documents."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from .. import audit
from ..config import settings
from ..database import get_db
from ..models import Notification, Role, SubmissionStatus, UploadedDocument, User
from ..schemas import notification_out
from ..security import get_current_user
from ..services import storage
from ..services.ocr import engine_status

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "error",
            "ocr": engine_status(), "bank_adapter": settings.bank_adapter + " (DEMO - no real bank contacted)"}


# ---------------- documents ----------------

@router.get("/documents/{doc_id}/file")
def download_document(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.get(UploadedDocument, doc_id)
    allowed = doc is not None and (
        (user.role == Role.INSTITUTION and doc.fdr.institution_id == user.institution_id)
        or (user.role != Role.INSTITUTION and doc.fdr.submission_status != SubmissionStatus.DRAFT)
    )
    if not allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    path = storage.resolve_stored(doc.stored_filename)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document file is missing from storage.")
    return FileResponse(path, media_type=doc.content_type, filename=doc.original_filename,
                        content_disposition_type="inline")


# ---------------- notifications ----------------

@router.get("/notifications")
def list_notifications(unread_only: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    rows = db.execute(stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(200)).scalars()
    return [notification_out(n) for n in rows]


@router.get("/notifications/unread-count")
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.execute(select(func.count()).select_from(Notification)
                   .where(Notification.user_id == user.id, Notification.is_read.is_(False))).scalar_one()
    return {"unread": n}


@router.post("/notifications/{nid}/read")
def mark_read(nid: int, read: bool = True, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if n is None or n.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found.")
    n.is_read = read
    db.commit()
    return notification_out(n)


@router.post("/notifications/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id).values(is_read=True))
    db.commit()
    return {"ok": True}


# ---------------- sample documents (fictional) ----------------

def _samples() -> list[Path]:
    d = Path(settings.samples_dir)
    return sorted(p for p in d.glob("*") if p.suffix.lower() in (".pdf", ".png", ".jpg")) if d.exists() else []


@router.get("/samples")
def list_samples(user: User = Depends(get_current_user)):
    return [{"name": p.name, "size_bytes": p.stat().st_size} for p in _samples()]


@router.get("/samples/{name}")
def get_sample(name: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    match = next((p for p in _samples() if p.name == name), None)  # only files listed in the folder
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sample not found.")
    media = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg"}[match.suffix.lower()]
    return FileResponse(match, media_type=media, filename=match.name)
