"""Password hashing (bcrypt) and JWT tokens, plus FastAPI dependencies for auth and RBAC."""
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import FDRRecord, Role, User

ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    payload = {"sub": str(user.id), "role": user.role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not signed in or session expired. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise unauthorized
    try:
        payload = jwt.decode(creds.credentials, settings.secret_key, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise unauthorized
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_roles(*roles: str):
    """Dependency factory: allow only the listed roles."""
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role is not permitted to perform this action.")
        return user
    return checker


STAFF_ROLES = (Role.OFFICER, Role.SENIOR, Role.ADMIN)
REVIEWER_ROLES = (Role.OFFICER, Role.SENIOR)


def get_fdr_for_user(db: Session, fdr_id: int, user: User) -> FDRRecord:
    """Load an FDR and enforce institution-level data isolation.

    Institutions get 404 (not 403) for other institutions' records so IDs are not confirmed to exist.
    """
    fdr = db.get(FDRRecord, fdr_id)
    if fdr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "FDR record not found.")
    if user.role == Role.INSTITUTION and fdr.institution_id != user.institution_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "FDR record not found.")
    return fdr
