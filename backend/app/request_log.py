"""Execution evidence for judges: every /api request is logged to the console, to data/logs/api.log,
and kept in a small in-memory ring buffer that the Live Evidence panel reads.

Only metadata is recorded (time, user, role, method, path, status, duration), never request bodies,
document contents or tokens.
"""
import itertools
import logging
import time
from collections import deque
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from jose import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .config import settings
from .database import SessionLocal
from .models import User

log = logging.getLogger("surakshafd.api")
_buffer: deque = deque(maxlen=300)
_ids = itertools.count(1)
_emails: dict[int, str] = {}
STARTED_AT = datetime.now(timezone.utc)

# Polling endpoints are counted but not logged, so the evidence feed shows real actions.
QUIET_PREFIXES = ("/api/demo/", "/api/notifications/unread-count", "/api/health")


def setup_logging() -> None:
    if log.handlers:
        return
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    log.addHandler(console)
    try:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(settings.log_dir / "api.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        log.addHandler(fh)
    except OSError:
        pass
    log.propagate = False


def _user_from_request(request: Request) -> tuple[int | None, str | None]:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None, None
    try:
        payload = jwt.decode(auth[7:], settings.secret_key, algorithms=["HS256"])
        return int(payload["sub"]), payload.get("role")
    except Exception:
        return None, None


def _email(user_id: int | None) -> str | None:
    if user_id is None:
        return None
    if user_id not in _emails:
        with SessionLocal() as db:
            u = db.get(User, user_id)
            _emails[user_id] = u.email if u else f"user#{user_id}"
    return _emails[user_id]


def forget_users() -> None:
    _emails.clear()


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            ms = round((time.perf_counter() - start) * 1000, 1)
            if not path.startswith(QUIET_PREFIXES):
                uid, role = _user_from_request(request)
                email = _email(uid)
                if path == "/api/auth/login":
                    email = getattr(request.state, "login_email", None)
                    role = "sign-in" if status == 200 else "failed sign-in"
                entry = {
                    "id": next(_ids),
                    "at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                    "method": request.method, "path": path, "status": status, "ms": ms,
                    "user_id": uid, "email": email, "role": role,
                }
                _buffer.append(entry)
                log.info("API %s %-6s %-52s %7.1f ms  %s", status, request.method, path, ms,
                         f"{email} ({role})" if email else "-")


def recent(since_id: int = 0, user_id: int | None = None, limit: int = 60) -> list[dict]:
    rows = [e for e in _buffer if e["id"] > since_id and (user_id is None or e["user_id"] == user_id)]
    return rows[-limit:][::-1]
