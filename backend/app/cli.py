"""Developer commands.

    python -m app.cli init-db       create tables (safe to re-run)
    python -m app.cli reset-demo    back up the database, wipe it, load fictional demo data (asks to confirm;
                                    add --yes to skip the question)
    python -m app.cli inspect       show live database contents: row counts, latest FDRs, latest audit entries
    python -m app.cli ensure-demo   load demo data only if the database is empty (used by Docker)
    python -m app.cli run-alerts    run the deadline alert job now
    python -m app.cli check-ocr     check Tesseract and OCR the sample FDR
"""
import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "help"
    if cmd == "init-db":
        from .init_db import create_all
        create_all()
        print("Database tables created.")
    elif cmd == "reset-demo":
        if "--yes" not in argv:
            answer = input("This backs up and then WIPES all SurakshaFD data, then reloads the demo data. "
                           "Type YES to continue: ")
            if answer.strip().upper() != "YES":
                print("Cancelled - nothing was changed.")
                return 1
        from .seed import DEMO_PASSWORD, reset_demo
        result = reset_demo()
        print(json.dumps(result, indent=2))
        print(f"\nDemo data loaded. All demo accounts use the DEVELOPMENT-ONLY password: {DEMO_PASSWORD}")
    elif cmd == "ensure-demo":
        from sqlalchemy import func, select
        from .database import SessionLocal
        from .init_db import create_all
        from .models import User
        create_all()
        with SessionLocal() as db:
            empty = db.execute(select(func.count()).select_from(User)).scalar_one() == 0
        if empty:
            from .seed import reset_demo
            reset_demo()
            print("Empty database - demo data loaded.")
        else:
            print("Database already has data - leaving it unchanged.")
    elif cmd == "run-alerts":
        from .database import SessionLocal
        from .init_db import create_all
        from .services.alerts import run_alerts
        create_all()
        with SessionLocal() as db:
            print(json.dumps(run_alerts(db), indent=2))
    elif cmd == "inspect":
        from sqlalchemy import func, select
        from .database import Base, SessionLocal, engine
        from .models import AuditLog, FDRRecord
        sys.stdout.reconfigure(encoding="utf-8")
        print(f"Database: {engine.url.render_as_string(hide_password=True)}\n")
        with SessionLocal() as db:
            print("Row counts")
            for t in Base.metadata.sorted_tables:
                print(f"  {t.name:28} {db.execute(select(func.count()).select_from(t)).scalar_one():>6}")
            print("\nLatest FDR records (most recently updated first)")
            for f in db.execute(select(FDRRecord).order_by(FDRRecord.updated_at.desc()).limit(5)).scalars():
                print(f"  {f.reference_no}  {str(f.fdr_number):24} Rs.{(f.principal_amount or 0):>12,.0f}  "
                      f"{f.submission_status}/{f.document_status}/bank:{f.bank_status}"
                      f"{' CLEARED' if f.is_cleared else ''}  updated {f.updated_at:%Y-%m-%d %H:%M:%S} UTC")
            print("\nLatest audit entries (append-only)")
            for a in db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(10)).scalars():
                print(f"  #{a.id:<5} {a.created_at:%Y-%m-%d %H:%M:%S} UTC  {str(a.user_email):30} {a.action:28} "
                      f"{(a.previous_status or '') + (' -> ' + a.new_status if a.new_status else '')}")
    elif cmd == "check-ocr":
        from .config import settings
        from .services.ocr import engine_status, run_ocr
        print(json.dumps(engine_status(), indent=2))
        sample = Path(settings.samples_dir) / "SAMPLE_FDR_Aravalli_10_Lakh.pdf"
        if sample.exists():
            r = run_ocr(sample.read_bytes(), "application/pdf")
            print(f"\n{r.status}: {r.message} ({r.duration_ms} ms, mean confidence {r.mean_confidence})")
            for f in r.fields:
                flag = "  <- needs review" if f.needs_review else ""
                print(f"  {f.field_name:18} {str(f.value):40} conf={f.confidence}{flag}")
        else:
            print("Sample not found - run reset-demo first.")
    else:
        print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
