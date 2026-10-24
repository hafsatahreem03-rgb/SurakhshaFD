"""Administrator: users, institutions, versioned policies, alert job trigger."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..database import get_db
from ..models import FDRRecord, Institution, PolicyRule, PolicyVersion, Role, User
from ..schemas import InstitutionIn, PolicyCreateIn, PolicyVersionIn, UserCreateIn, UserUpdateIn, user_out
from ..security import STAFF_ROLES, get_current_user, hash_password, require_roles
from ..services.alerts import run_alerts
from ..services.policy import get_policy

router = APIRouter(prefix="/api", tags=["admin"])
admin_only = require_roles(Role.ADMIN)


# ---------------- institutions ----------------

def institution_out(db: Session, i: Institution) -> dict:
    fdr_count, amount = db.execute(
        select(func.count(FDRRecord.id), func.coalesce(func.sum(FDRRecord.principal_amount), 0))
        .where(FDRRecord.institution_id == i.id)).one()
    return {"id": i.id, "name": i.name, "code": i.code, "city": i.city, "state": i.state,
            "contact_email": i.contact_email, "is_active": i.is_active, "fdr_count": fdr_count,
            "total_amount": amount, "user_count": len(i.users), "created_at": i.created_at.isoformat()}


@router.get("/institutions")
def list_institutions(user: User = Depends(require_roles(*STAFF_ROLES)), db: Session = Depends(get_db)):
    return [institution_out(db, i) for i in db.execute(select(Institution).order_by(Institution.name)).scalars()]


@router.post("/institutions", status_code=201)
def create_institution(body: InstitutionIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    if db.execute(select(Institution).where((Institution.name == body.name) | (Institution.code == body.code))).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An institution with this name or code already exists.")
    inst = Institution(**body.model_dump())
    db.add(inst)
    db.flush()
    audit.record(db, user, "institution_created", f"Institution created: {inst.name}", entity_type="institution",
                 entity_id=inst.id)
    db.commit()
    return institution_out(db, inst)


# ---------------- users ----------------

@router.get("/admin/users")
def list_users(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return [user_out(u) for u in db.execute(select(User).order_by(User.role, User.email)).scalars()]


@router.post("/admin/users", status_code=201)
def create_user(body: UserCreateIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.execute(select(User).where(func.lower(User.email) == email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists.")
    if body.role == Role.INSTITUTION:
        if not body.institution_id or db.get(Institution, body.institution_id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Institution users must be linked to an institution.")
    elif body.institution_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only institution users can be linked to an institution.")
    u = User(email=email, full_name=body.full_name, role=body.role, institution_id=body.institution_id,
             password_hash=hash_password(body.password))
    db.add(u)
    db.flush()
    audit.record(db, user, "user_created", f"User created: {email} ({body.role})", entity_type="user", entity_id=u.id)
    db.commit()
    return user_out(u)


@router.patch("/admin/users/{uid}")
def update_user(uid: int, body: UserUpdateIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    if u.id == user.id and body.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account.")
    changes = []
    if body.full_name is not None:
        u.full_name = body.full_name
        changes.append("name")
    if body.is_active is not None and body.is_active != u.is_active:
        u.is_active = body.is_active
        changes.append("activated" if body.is_active else "deactivated")
    if body.password:
        u.password_hash = hash_password(body.password)
        changes.append("password reset")
    audit.record(db, user, "user_updated", f"User {u.email}: {', '.join(changes) or 'no changes'}",
                 entity_type="user", entity_id=u.id)
    db.commit()
    return user_out(u)


# ---------------- policies ----------------

def policy_out(r: PolicyRule, current: dict) -> dict:
    return {
        "id": r.id, "key": r.key, "name": r.name, "category": r.category, "description": r.description,
        "current_value": current,
        "versions": [{"id": v.id, "version": v.version, "value": v.value, "effective_from": v.effective_from.isoformat(),
                      "change_note": v.change_note, "created_by": v.created_by.full_name if v.created_by else "System seed",
                      "created_at": v.created_at.isoformat()} for v in reversed(r.versions)],
    }


@router.get("/policies")
def list_policies(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rules = db.execute(select(PolicyRule).order_by(PolicyRule.category, PolicyRule.key)).scalars()
    return [policy_out(r, get_policy(db, r.key)) for r in rules]


@router.post("/policies", status_code=201)
def create_policy(body: PolicyCreateIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    if db.execute(select(PolicyRule).where(PolicyRule.key == body.key)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "A policy with this key already exists.")
    r = PolicyRule(key=body.key, name=body.name, category=body.category, description=body.description)
    db.add(r)
    db.flush()
    db.add(PolicyVersion(rule_id=r.id, version=1, value=body.value, effective_from=body.effective_from,
                         change_note=body.change_note, created_by_id=user.id))
    audit.record(db, user, "policy_created", f"Policy created: {body.key}", entity_type="policy", entity_id=r.id,
                 new_status="v1", details={"value": body.value, "effective_from": body.effective_from.isoformat()})
    db.commit()
    db.refresh(r)
    return policy_out(r, get_policy(db, r.key))


@router.post("/policies/{key}/versions", status_code=201)
def add_policy_version(key: str, body: PolicyVersionIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    r = db.execute(select(PolicyRule).where(PolicyRule.key == key)).scalar_one_or_none()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found.")
    _check_policy_value(key, body.value)
    last = r.versions[-1] if r.versions else None
    v = PolicyVersion(rule_id=r.id, version=(last.version + 1) if last else 1, value=body.value,
                      effective_from=body.effective_from, change_note=body.change_note, created_by_id=user.id)
    db.add(v)
    audit.record(db, user, "policy_version_added", f"Policy {key} updated to v{v.version}: {body.change_note}",
                 entity_type="policy", entity_id=r.id,
                 previous_status=f"v{last.version}" if last else None, new_status=f"v{v.version}",
                 details={"old_value": last.value if last else None, "new_value": body.value,
                          "effective_from": body.effective_from.isoformat()})
    db.commit()
    db.refresh(r)
    return policy_out(r, get_policy(db, key))


def _check_policy_value(key: str, value: dict) -> None:
    """Light type checks for the built-in policies so a typo cannot break validation."""
    def bad(msg):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, msg)
    if key == "alert_intervals":
        days = value.get("days_before_maturity")
        if not isinstance(days, list) or not all(isinstance(d, int) and 0 < d <= 365 for d in days):
            bad("days_before_maturity must be a list of whole numbers between 1 and 365.")
    if key == "required_documents":
        docs = value.get("documents")
        if not isinstance(docs, list) or not all(d in ("fdr_receipt", "payment_proof", "lien_letter", "other") for d in docs):
            bad("documents must be a list using: fdr_receipt, payment_proof, lien_letter, other.")
    if key == "deposit_requirements":
        for k in ("minimum_principal", "minimum_tenure_days"):
            if k in value and not isinstance(value[k], (int, float)):
                bad(f"{k} must be a number.")


# ---------------- alert job ----------------

@router.post("/admin/run-alerts")
def trigger_alerts(user: User = Depends(require_roles(Role.ADMIN, Role.OFFICER)), db: Session = Depends(get_db)):
    result = run_alerts(db)
    audit.record(db, user, "alerts_run", f"Deadline alert check run manually: {result}")
    db.commit()
    return result
