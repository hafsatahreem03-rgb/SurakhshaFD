"""Dashboards, analytics and CSV export."""
import csv
import io
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    AuditLog, BankStatus, ClearanceRequest, ClearanceStatus, DocumentStatus, FDRRecord, Institution, Role,
    SubmissionStatus, User, utcnow,
)
from ..schemas import audit_out, fdr_summary
from ..security import STAFF_ROLES, get_current_user, require_roles
from ..services.validation import latest_results
from ..services.workflow import overall_stage

router = APIRouter(prefix="/api", tags=["reports"])


def scoped_fdrs(db: Session, user: User, institution_id: int | None = None, stage: str | None = None,
                date_from: date | None = None, date_to: date | None = None) -> list[FDRRecord]:
    stmt = select(FDRRecord)
    if user.role == Role.INSTITUTION:
        stmt = stmt.where(FDRRecord.institution_id == user.institution_id)
    else:
        stmt = stmt.where(FDRRecord.submission_status != SubmissionStatus.DRAFT)
        if institution_id:
            stmt = stmt.where(FDRRecord.institution_id == institution_id)
    if date_from:
        stmt = stmt.where(FDRRecord.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        stmt = stmt.where(FDRRecord.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    rows = list(db.execute(stmt.order_by(FDRRecord.id)).scalars())
    if stage:
        rows = [f for f in rows if overall_stage(f) == stage]
    return rows


def _activity(db: Session, user: User, limit: int = 12) -> list[dict]:
    stmt = select(AuditLog).where(AuditLog.fdr_id.is_not(None)).order_by(AuditLog.id.desc()).limit(limit)
    if user.role == Role.INSTITUTION:
        stmt = (select(AuditLog).join(FDRRecord, AuditLog.fdr_id == FDRRecord.id)
                .where(FDRRecord.institution_id == user.institution_id).order_by(AuditLog.id.desc()).limit(limit))
    out = []
    for a in db.execute(stmt).scalars():
        d = audit_out(a)
        f = db.get(FDRRecord, a.fdr_id) if a.fdr_id else None
        d["reference_no"] = f.reference_no if f else None
        out.append(d)
    return out


@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fdrs = scoped_fdrs(db, user)
    today = date.today()
    submitted = [f for f in fdrs if f.submission_status != SubmissionStatus.DRAFT]
    active = [f for f in submitted if not f.is_cleared and f.document_status != DocumentStatus.REJECTED]

    def has_issue(f: FDRRecord) -> bool:
        return (f.document_status == DocumentStatus.DISCREPANCY or f.bank_status == BankStatus.MISMATCH
                or any(r.severity == "warning" for r in latest_results(db, f.id)))

    cr_stmt = select(ClearanceRequest).join(FDRRecord)
    if user.role == Role.INSTITUTION:
        cr_stmt = cr_stmt.where(FDRRecord.institution_id == user.institution_id)
    crs = list(db.execute(cr_stmt).scalars())
    maturing = sorted([f for f in active if f.maturity_date and 0 <= (f.maturity_date - today).days <= 60],
                      key=lambda f: f.maturity_date)
    matured = [f for f in active if f.maturity_date and f.maturity_date < today]

    cards = {
        "total_fdrs": len(fdrs),
        "submitted_fdrs": len(submitted),
        "total_amount": sum(f.principal_amount or 0 for f in submitted),
        "pending_document_review": sum(f.document_status in (DocumentStatus.PENDING_REVIEW, DocumentStatus.DISCREPANCY) for f in active),
        "pending_verification": sum(f.bank_status in (BankStatus.NOT_STARTED, BankStatus.PENDING) for f in active),
        "discrepancies": sum(has_issue(f) for f in active),
        "bank_confirmed": sum(f.bank_status == BankStatus.CONFIRMED for f in submitted),
        "approaching_maturity": len(maturing),
        "matured": len(matured),
        "pending_clearance": sum(c.status == ClearanceStatus.PENDING_OFFICER_REVIEW for c in crs),
        "awaiting_final_decision": sum(c.status in (ClearanceStatus.RECOMMENDED_APPROVAL, ClearanceStatus.RECOMMENDED_REJECTION) for c in crs),
        "cleared": sum(f.is_cleared for f in fdrs),
        "drafts": sum(f.submission_status == SubmissionStatus.DRAFT for f in fdrs),
        "correction_requested": sum(f.submission_status == SubmissionStatus.CORRECTION_REQUESTED for f in fdrs),
        "overdue_reviews": sum(1 for f in active if f.document_status in (DocumentStatus.PENDING_REVIEW, DocumentStatus.DISCREPANCY)
                               and f.review_due_at and f.review_due_at < utcnow()),
        "clearances_approved": sum(c.status == ClearanceStatus.APPROVED for c in crs),
        "clearances_rejected": sum(c.status == ClearanceStatus.REJECTED for c in crs),
    }
    if user.role == Role.ADMIN:
        cards["institutions"] = db.execute(select(func.count()).select_from(Institution)).scalar_one()
        cards["users"] = db.execute(select(func.count()).select_from(User)).scalar_one()

    stage_counts = Counter(overall_stage(f) for f in fdrs)
    bank_counts = Counter(f.bank_status for f in submitted)
    return {
        "cards": cards,
        "stage_distribution": [{"stage": k, "count": v} for k, v in stage_counts.most_common()],
        "bank_distribution": [{"status": k, "count": v} for k, v in bank_counts.most_common()],
        "upcoming_maturities": [fdr_summary(f) for f in maturing[:8]],
        "recent_fdrs": [fdr_summary(f) for f in sorted(fdrs, key=lambda f: f.updated_at, reverse=True)[:8]],
        "recent_activity": _activity(db, user),
    }


@router.get("/reports/summary")
def report_summary(institution_id: int | None = None, stage: str | None = None,
                   date_from: date | None = None, date_to: date | None = None,
                   user: User = Depends(require_roles(*STAFF_ROLES)), db: Session = Depends(get_db)):
    fdrs = scoped_fdrs(db, user, institution_id, stage, date_from, date_to)
    by_inst: dict[str, dict] = defaultdict(lambda: {"count": 0, "amount": 0.0})
    timeline: dict[str, dict] = defaultdict(lambda: {"count": 0, "amount": 0.0})
    submissions: Counter = Counter()
    issues: Counter = Counter()
    for f in fdrs:
        b = by_inst[f.institution.name]
        b["count"] += 1
        b["amount"] += f.principal_amount or 0
        if f.maturity_date:
            t = timeline[f.maturity_date.strftime("%Y-%m")]
            t["count"] += 1
            t["amount"] += f.principal_amount or 0
        submissions[(f.submitted_at or f.created_at).strftime("%Y-%m")] += 1
        for r in latest_results(db, f.id):
            if r.severity in ("error", "warning"):
                issues[r.check_code] += 1
    ids = [f.id for f in fdrs]
    crs = list(db.execute(select(ClearanceRequest).where(ClearanceRequest.fdr_id.in_(ids))).scalars()) if ids else []
    return {
        "total_count": len(fdrs),
        "total_amount": sum(f.principal_amount or 0 for f in fdrs),
        "stage_distribution": [{"name": k, "value": v} for k, v in Counter(overall_stage(f) for f in fdrs).most_common()],
        "document_status": [{"name": k, "value": v} for k, v in Counter(f.document_status for f in fdrs).most_common()],
        "bank_status": [{"name": k, "value": v} for k, v in Counter(f.bank_status for f in fdrs).most_common()],
        "by_institution": sorted([{"name": k, **v} for k, v in by_inst.items()], key=lambda x: -x["amount"]),
        "maturity_timeline": [{"month": k, **v} for k, v in sorted(timeline.items())],
        "submissions_by_month": [{"month": k, "count": v} for k, v in sorted(submissions.items())],
        "clearance_status": [{"name": k, "value": v} for k, v in Counter(c.status for c in crs).most_common()],
        "validation_issues": [{"name": k, "value": v} for k, v in issues.most_common()],
        "pending_cases": sum(1 for f in fdrs if not f.is_cleared and f.document_status in
                             (DocumentStatus.PENDING_REVIEW, DocumentStatus.DISCREPANCY)),
    }


def _csv_response(header: list[str], rows: list[list], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    buf.seek(0)
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/reports/fdrs.csv")
def export_fdrs(institution_id: int | None = None, stage: str | None = None,
                date_from: date | None = None, date_to: date | None = None,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    fdrs = scoped_fdrs(db, user, institution_id, stage, date_from, date_to)
    header = ["Reference", "Institution", "FDR number", "Bank (fictional)", "Branch", "Principal (INR)",
              "Interest %", "Issue date", "Maturity date", "Stage", "Document status", "Bank status (simulated)",
              "Cleared (demo)"]
    rows = [[f.reference_no, f.institution.name, f.fdr_number, f.bank_name, f.branch_name, f.principal_amount,
             f.interest_rate, f.issue_date, f.maturity_date, overall_stage(f), f.document_status, f.bank_status,
             "yes" if f.is_cleared else "no"] for f in fdrs]
    return _csv_response(header, rows, f"surakshafd-fdrs-{date.today()}.csv")


@router.get("/audit")
def list_audit(action: str | None = None, fdr_id: int | None = None, user_email: str | None = None,
               date_from: date | None = None, date_to: date | None = None,
               limit: int = Query(200, ge=1, le=2000),
               user: User = Depends(require_roles(*STAFF_ROLES)), db: Session = Depends(get_db)):
    stmt = _audit_query(action, fdr_id, user_email, date_from, date_to).limit(limit)
    out = []
    for a in db.execute(stmt).scalars():
        d = audit_out(a)
        f = db.get(FDRRecord, a.fdr_id) if a.fdr_id else None
        d["reference_no"] = f.reference_no if f else None
        out.append(d)
    return out


def _audit_query(action, fdr_id, user_email, date_from, date_to):
    stmt = select(AuditLog).order_by(AuditLog.id.desc())
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if fdr_id:
        stmt = stmt.where(AuditLog.fdr_id == fdr_id)
    if user_email:
        stmt = stmt.where(AuditLog.user_email.ilike(f"%{user_email}%"))
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        stmt = stmt.where(AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    return stmt


@router.get("/audit/actions")
def audit_actions(user: User = Depends(require_roles(*STAFF_ROLES)), db: Session = Depends(get_db)):
    return sorted(r[0] for r in db.execute(select(AuditLog.action).distinct()))


@router.get("/audit/export.csv")
def export_audit(action: str | None = None, fdr_id: int | None = None, user_email: str | None = None,
                 date_from: date | None = None, date_to: date | None = None,
                 user: User = Depends(require_roles(Role.ADMIN, Role.SENIOR)), db: Session = Depends(get_db)):
    rows = db.execute(_audit_query(action, fdr_id, user_email, date_from, date_to)).scalars()
    data = [[a.id, a.created_at.isoformat(timespec="seconds"), a.user_email, a.role, a.action, a.fdr_id,
             a.previous_status, a.new_status, a.description] for a in rows]
    return _csv_response(["ID", "Timestamp (UTC)", "User", "Role", "Action", "FDR ID", "Previous status",
                          "New status", "Description"], data, f"surakshafd-audit-{date.today()}.csv")
