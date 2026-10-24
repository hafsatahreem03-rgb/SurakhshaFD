"""Judge Demonstration Mode: live execution evidence (API calls, database rows, audit) and a safe demo reset.

Enabled only when DEMO_MODE=true. Institution users see only their own requests and their own records,
the same isolation rule as the rest of the API.
"""
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit, request_log
from ..config import settings
from ..database import Base, engine, get_db
from ..models import AuditLog, FDRRecord, Role, User
from ..schemas import audit_out
from ..security import get_current_user, require_roles

router = APIRouter(prefix="/api/demo", tags=["judge-demo"])


def _enabled():
    if not settings.demo_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Judge Demonstration Mode is disabled.")


def _db_file() -> Path | None:
    if engine.dialect.name != "sqlite" or not engine.url.database:
        return None
    return Path(engine.url.database).resolve()


@router.get("/config")
def demo_config(user: User = Depends(get_current_user)):
    db_file = _db_file()
    return {
        "demo_mode": settings.demo_mode,
        "database": engine.dialect.name,
        "database_file": str(db_file) if db_file and settings.demo_mode else None,
        "api_log_file": str((settings.log_dir / "api.log").resolve()) if settings.demo_mode else None,
        "server_started_at": request_log.STARTED_AT.isoformat(timespec="seconds"),
        "bank_adapter": f"{settings.bank_adapter} (SIMULATED - no real bank is contacted)",
    }


@router.get("/requests", dependencies=[Depends(_enabled)])
def demo_requests(since_id: int = Query(0, ge=0), user: User = Depends(get_current_user)):
    only = user.id if user.role == Role.INSTITUTION else None
    return request_log.recent(since_id, only)


@router.get("/db", dependencies=[Depends(_enabled)])
def demo_db(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Live row counts plus the latest FDR rows and audit entries, read straight from the database."""
    counts = {t.name: db.execute(select(func.count()).select_from(t)).scalar_one()
              for t in Base.metadata.sorted_tables}
    fdr_q = select(FDRRecord).order_by(FDRRecord.updated_at.desc()).limit(6)
    audit_q = select(AuditLog).order_by(AuditLog.id.desc()).limit(12)
    if user.role == Role.INSTITUTION:
        fdr_q = fdr_q.where(FDRRecord.institution_id == user.institution_id)
        audit_q = (select(AuditLog).join(FDRRecord, AuditLog.fdr_id == FDRRecord.id)
                   .where(FDRRecord.institution_id == user.institution_id).order_by(AuditLog.id.desc()).limit(12))
    db_file = _db_file()
    stat = db_file.stat() if db_file and db_file.exists() else None
    return {
        "read_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "database_file": str(db_file) if db_file else None,
        "database_bytes": stat.st_size if stat else None,
        "database_modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds") if stat else None,
        "row_counts": counts,
        "latest_fdr_rows": [{
            "id": f.id, "reference_no": f.reference_no, "institution": f.institution.name,
            "fdr_number": f.fdr_number, "principal_amount": f.principal_amount,
            "submission_status": f.submission_status, "document_status": f.document_status,
            "bank_status": f.bank_status, "is_cleared": f.is_cleared,
            "updated_at": f.updated_at.isoformat(timespec="seconds"),
        } for f in db.execute(fdr_q).scalars()],
        "latest_audit": [audit_out(a) for a in db.execute(audit_q).scalars()],
    }


class ResetIn(BaseModel):
    confirm: str


@router.post("/reset", dependencies=[Depends(_enabled)])
async def demo_reset(body: ResetIn, user: User = Depends(require_roles(Role.ADMIN))):
    if body.confirm != "RESET":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Type RESET to confirm. This wipes all demo data.')
    from ..seed import reset_demo  # local import: seeding pulls in report/PDF libraries
    result = await run_in_threadpool(reset_demo)
    request_log.forget_users()
    from ..database import SessionLocal
    with SessionLocal() as db:  # first entry of the fresh audit log records who reset it
        admin = db.execute(select(User).where(User.email == user.email)).scalar_one_or_none()
        audit.record(db, admin, "demo_reset", f"Demo data reset from the Live Evidence panel. Backup: {result.get('backup')}")
        db.commit()
    return result
