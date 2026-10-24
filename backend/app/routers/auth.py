from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..database import get_db
from ..models import User, utcnow
from ..schemas import LoginIn, user_out
from ..security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    request.state.login_email = email  # lets the request log show who signed in (or tried to)
    user = db.execute(select(User).where(func.lower(User.email) == email)).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        audit.record(db, None, "login_failed", "Failed login attempt", email=email[:200])
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not user.is_active:
        audit.record(db, user, "login_blocked", "Login attempt on a deactivated account")
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated. Contact the administrator.")
    user.last_login_at = utcnow()
    audit.record(db, user, "login", f"{user.full_name} signed in")
    db.commit()
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": user_out(user)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # JWTs are stateless; the client discards the token. We record the event for the audit trail.
    audit.record(db, user, "logout", f"{user.full_name} signed out")
    db.commit()
    return {"ok": True}
