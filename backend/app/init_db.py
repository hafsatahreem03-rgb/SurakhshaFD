"""Reproducible database initialisation: creates tables and append-only audit triggers."""
from sqlalchemy import text

from . import models  # noqa: F401  (register models)
from .database import Base, engine

AUDIT_TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS audit_logs_no_update BEFORE UPDATE ON audit_logs
       BEGIN SELECT RAISE(ABORT, 'audit_logs is append-only'); END;""",
    """CREATE TRIGGER IF NOT EXISTS audit_logs_no_delete BEFORE DELETE ON audit_logs
       BEGIN SELECT RAISE(ABORT, 'audit_logs is append-only'); END;""",
]


def create_all(bind=engine) -> None:
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name == "sqlite":
        with bind.begin() as conn:
            for stmt in AUDIT_TRIGGERS:
                conn.execute(text(stmt))


def drop_all(bind=engine) -> None:
    Base.metadata.drop_all(bind=bind)
