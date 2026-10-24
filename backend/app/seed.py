"""Reset the database and load FICTIONAL demonstration data.

    python -m app.cli reset-demo

All institutions, banks, people, numbers and amounts are synthetic. Dates are relative to today,
so maturity alerts (60/30/7 days) always show up during a demo.
"""
import zlib
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from . import audit
from .config import settings
from .database import SessionLocal, engine
from .init_db import create_all, drop_all
from .models import (
    ApprovalDecision, BankVerification, ClearanceRequest, ClearanceStatus, DocType, DocumentStatus, ExtractedField,
    FDRRecord, Institution, Role, SubmissionStatus, UploadedDocument, User, utcnow,
)
from .sample_docs import (
    fdr_receipt_pdf, payment_proof_pdf, pdf_to_phone_photo_jpg, pdf_to_scanned_png, simulated_bank_letter_pdf,
    term_deposit_advice_pdf,
)
from .security import hash_password
from .services import storage
from .services.alerts import run_alerts
from .services.policy import ensure_default_policies
from .services.validation import run_validation

DEMO_PASSWORD = "Demo@123"  # DEVELOPMENT ONLY

INSTITUTIONS = [
    ("Aravalli Institute of Technology (Demo)", "DEMO-AIT-01", "Jaipur", "Rajasthan", "aravalli"),
    ("Godavari College of Engineering (Demo)", "DEMO-GCE-02", "Nashik", "Maharashtra", "godavari"),
    ("Narmada Polytechnic (Demo)", "DEMO-NP-03", "Jabalpur", "Madhya Pradesh", "narmada"),
    ("Konark School of Management (Demo)", "DEMO-KSM-04", "Bhubaneswar", "Odisha", "konark"),
    ("Brahmaputra Institute of Pharmacy (Demo)", "DEMO-BIP-05", "Guwahati", "Assam", "brahmaputra"),
]
INST_CONTACTS = ["Priya Sharma", "Arjun Kulkarni", "Neha Patel", "Sanjay Mohanty", "Ritu Baruah"]

STAFF = [
    ("officer@demo.surakshafd.in", "Rahul Verma", Role.OFFICER),
    ("officer2@demo.surakshafd.in", "Anita Desai", Role.OFFICER),
    ("senior@demo.surakshafd.in", "Dr. S. K. Rao", Role.SENIOR),
    ("senior2@demo.surakshafd.in", "Meera Iyer", Role.SENIOR),
    ("admin@demo.surakshafd.in", "System Administrator", Role.ADMIN),
]

BANKS = {
    "SDCB": ("Sahyadri Demo Co-operative Bank", "Pune Camp Branch"),
    "BSB": ("Bharat Sample Bank", "MI Road Branch"),
    "GVDB": ("Ganga Valley Demo Bank", "Civil Lines Branch"),
    "DFB": ("Deccan Fictional Bank", "Station Road Branch"),
}

# The number used by the live-demo sample PDF - never used by seeded records.
LIVE_DEMO_FDR_NUMBER = "SDCB/FDR/2026/004817"
# Judge Demonstration Mode: two fresh FDRs that never collide with seeded or sample records.
JUDGE_DEMO1 = {"number": "SDCB/FDR/2026/005120", "principal": 1000000, "rate": 7.30, "issue_ago": 12, "tenure": 730}
JUDGE_DEMO2 = {"number": "GVDB/TD/2026/007352", "principal": 750000, "rate": 7.10, "issue_ago": 8, "tenure": 1095,
               "words": "Rupees Seven Lakh Fifty Thousand Only", "customer_id": "CIF-0088213"}


def _ts(days_ago: float, hour: int = 11) -> datetime:
    """A UTC-naive timestamp `days_ago` days back, at a working hour."""
    d = utcnow() - timedelta(days=days_ago)
    return d.replace(hour=hour, minute=(int(days_ago * 37) % 60), second=0, microsecond=0)


def _log(db, user, action, desc, fdr, when, **kw):
    entry = audit.record(db, user, action, desc, fdr_id=fdr.id if fdr else None, **kw)
    entry.created_at = when
    return entry


class Seeder:
    def __init__(self, db: Session):
        self.db = db
        self.today = date.today()
        self.users: dict[str, User] = {}
        self.inst: dict[str, Institution] = {}

    # ---------- people ----------
    def people(self):
        for (name, code, city, state, slug), contact in zip(INSTITUTIONS, INST_CONTACTS):
            i = Institution(name=name, code=code, city=city, state=state, contact_email=f"{slug}@demo.surakshafd.in")
            self.db.add(i)
            self.db.flush()
            self.inst[slug] = i
            u = User(email=f"{slug}@demo.surakshafd.in", full_name=f"{contact} ({name.split(' (')[0].split()[0]})",
                     role=Role.INSTITUTION, institution_id=i.id, password_hash=hash_password(DEMO_PASSWORD))
            self.db.add(u)
            self.users[slug] = u
        for email, name, role in STAFF:
            u = User(email=email, full_name=name, role=role, password_hash=hash_password(DEMO_PASSWORD))
            self.db.add(u)
            self.users[email.split("@")[0]] = u
        self.db.flush()
        ensure_default_policies(self.db, self.today - timedelta(days=365), self.users["admin"].id)

    # ---------- documents ----------
    def add_doc(self, fdr: FDRRecord, doc_type: str, data: bytes, name: str, by: User, when: datetime,
                ext: str = ".pdf") -> UploadedDocument:
        import hashlib
        stored = storage.save_bytes(data, ext)
        doc = UploadedDocument(fdr_id=fdr.id, doc_type=doc_type, original_filename=name, stored_filename=stored,
                               content_type="application/pdf" if ext == ".pdf" else "image/png",
                               size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                               uploaded_by_id=by.id, uploaded_at=when)
        self.db.add(doc)
        self.db.flush()
        _log(self.db, by, "document_uploaded", f"Uploaded {doc_type.replace('_', ' ')}: {name}", fdr, when,
             entity_type="document", entity_id=doc.id, details={"doc_type": doc_type, "size_bytes": len(data)})
        return doc

    # ---------- one FDR ----------
    def fdr(self, slug: str, bank: str, number: str, principal: float, rate: float, issue_ago: int, tenure_days: int,
            *, doc_principal: float | None = None, created_ago: float = 20, submit: bool = True,
            payment_proof: bool = True) -> FDRRecord:
        inst, user = self.inst[slug], self.users[slug]
        bank_name, branch = BANKS[bank]
        issue = self.today - timedelta(days=issue_ago)
        maturity = issue + timedelta(days=tenure_days)
        holder = inst.name.replace(" (Demo)", "")
        acct = f"XXXXXX{zlib.crc32(number.encode()) % 9000 + 1000}"
        f = FDRRecord(reference_no="TMP", institution_id=inst.id, created_by_id=user.id, fdr_number=number,
                      bank_name=bank_name, branch_name=branch, account_holder=holder, account_number_masked=acct,
                      principal_amount=principal, interest_rate=rate, issue_date=issue, maturity_date=maturity,
                      created_at=_ts(created_ago, 10))
        self.db.add(f)
        self.db.flush()
        f.reference_no = f"SFD-{self.today.year}-{f.id:04d}"
        created = _ts(created_ago, 10)
        _log(self.db, user, "fdr_created", f"Draft {f.reference_no} created", f, created, entity_type="fdr",
             entity_id=f.id, new_status="draft")

        pdf = fdr_receipt_pdf(bank=bank_name, branch=branch, fdr_number=number, institution=holder, holder=holder,
                              account_masked=acct, principal=doc_principal or principal, rate=rate, issue=issue,
                              maturity=maturity)
        doc = self.add_doc(f, DocType.FDR_RECEIPT, pdf, f"FDR_{number.replace('/', '-')}.pdf", user, created)
        doc.ocr_status, doc.ocr_engine = "completed", "seed data (pre-extracted for demo)"
        doc.ocr_mean_confidence, doc.ocr_duration_ms = 93.4, 0
        doc.ocr_message = "Seeded record: values pre-extracted. Upload a new document to see live OCR."
        doc.ocr_text = "(seeded record - live OCR text appears for documents uploaded through the portal)"
        values = {
            "institution_name": holder, "bank_name": bank_name, "branch_name": branch, "fdr_number": number,
            "account_holder": holder, "principal_amount": f"{(doc_principal or principal):.2f}",
            "issue_date": issue.isoformat(), "maturity_date": maturity.isoformat(), "interest_rate": f"{rate:.2f}",
        }
        for k, v in values.items():
            self.db.add(ExtractedField(document_id=doc.id, fdr_id=f.id, field_name=k, extracted_value=v,
                                       confidence=95.0 if k != "branch_name" else 64.0,
                                       needs_review=k == "branch_name", confirmed_value=v if submit else None,
                                       is_confirmed=submit))
        _log(self.db, user, "ocr_completed", "Fields extracted from FDR receipt (seeded)", f, created,
             entity_type="document", entity_id=doc.id)
        if payment_proof:
            self.add_doc(f, DocType.PAYMENT_PROOF,
                         payment_proof_pdf(bank=bank_name, institution=holder, fdr_number=number,
                                           principal=principal, paid_on=issue, txn=f"NEFT{f.id:06d}DEMO"),
                         f"Payment_Proof_{f.reference_no}.pdf", user, created)
        self.db.flush()
        if submit:
            when = _ts(created_ago - 0.2, 12)
            results = run_validation(self.db, f)
            warn = sum(r["severity"] == "warning" for r in results)
            f.submission_status, f.document_status = SubmissionStatus.SUBMITTED, DocumentStatus.PENDING_REVIEW
            f.submitted_at, f.review_due_at = when, when + timedelta(days=7)
            _log(self.db, user, "fdr_submitted", f"{f.reference_no} submitted with {warn} warning(s) for officer review",
                 f, when, entity_type="fdr", entity_id=f.id, previous_status="draft/not_submitted",
                 new_status="submitted/pending_review")
        return f

    def review(self, f: FDRRecord, action: str, remarks: str, days_ago: float, by: str = "officer"):
        status_for = {"mark_checked": DocumentStatus.DOCUMENT_CHECKED, "mark_discrepancy": DocumentStatus.DISCREPANCY,
                      "request_correction": DocumentStatus.CORRECTION_REQUESTED}
        prev = f.document_status
        f.document_status = status_for[action]
        f.last_review_remarks = remarks
        f.assigned_officer_id = self.users[by].id
        if action == "request_correction":
            f.submission_status = SubmissionStatus.CORRECTION_REQUESTED
        _log(self.db, self.users[by], f"review_{action}", remarks, f, _ts(days_ago, 14), entity_type="fdr",
             entity_id=f.id, previous_status=prev, new_status=f.document_status)

    def bank(self, f: FDRRecord, outcome: str, remarks: str, days_ago: float, by: str = "officer", evidence=False):
        ev_id = None
        if evidence:
            ev = self.add_doc(f, DocType.BANK_EVIDENCE,
                              simulated_bank_letter_pdf(bank=f.bank_name, fdr_number=f.fdr_number,
                                                        institution=f.account_holder, principal=f.principal_amount,
                                                        on=self.today - timedelta(days=int(days_ago))),
                              f"Simulated_Bank_Letter_{f.reference_no}.pdf", self.users[by], _ts(days_ago, 15))
            ev_id = ev.id
        ref = f"SIM-{(self.today - timedelta(days=int(days_ago))):%Y%m%d}-{f.id:03d}A{len(outcome)}"
        v = BankVerification(fdr_id=f.id, outcome=outcome, adapter="simulated-demo", is_simulated=True, reference=ref,
                             remarks=remarks, response_summary=f"DEMO / SIMULATED outcome: {outcome}. No real bank was contacted.",
                             evidence_document_id=ev_id, officer_id=self.users[by].id, created_at=_ts(days_ago, 15))
        self.db.add(v)
        prev = f.bank_status
        f.bank_status = outcome
        self.db.flush()
        _log(self.db, self.users[by], "bank_verification_simulated",
             f"[DEMO / SIMULATED] Bank verification outcome: {outcome} (ref {ref})", f, _ts(days_ago, 15),
             entity_type="bank_verification", entity_id=v.id, previous_status=prev, new_status=outcome)

    def clearance(self, f: FDRRecord, reason: str, days_ago: float, recommend: tuple | None = None,
                  decide: tuple | None = None) -> ClearanceRequest:
        slug = next(k for k, v in self.inst.items() if v.id == f.institution_id)
        cr = ClearanceRequest(fdr_id=f.id, requested_by_id=self.users[slug].id, reason=reason,
                              created_at=_ts(days_ago, 11),
                              prerequisite_snapshot={"eligible": True, "checks": [
                                  {"code": "SUBMITTED", "label": "FDR has been submitted", "ok": True},
                                  {"code": "DOCUMENT_CHECKED", "label": "Documents checked by an AICTE officer", "ok": True},
                                  {"code": "BANK_CONFIRMED", "label": "Bank verification confirmed (simulated in demo)", "ok": True}]})
        self.db.add(cr)
        self.db.flush()
        _log(self.db, self.users[slug], "clearance_requested", f"Clearance requested: {reason}", f, _ts(days_ago, 11),
             entity_type="clearance_request", entity_id=cr.id, new_status=cr.status)
        if recommend:
            who, rec, remarks, ago = recommend
            cr.recommended_by_id, cr.recommendation, cr.recommendation_remarks = self.users[who].id, rec, remarks
            cr.recommended_at = _ts(ago, 13)
            prev = cr.status
            cr.status = ClearanceStatus.RECOMMENDED_APPROVAL if rec == "approve" else ClearanceStatus.RECOMMENDED_REJECTION
            _log(self.db, self.users[who], "clearance_recommended",
                 f"Officer recommended {'APPROVAL' if rec == 'approve' else 'REJECTION'}: {remarks}", f, _ts(ago, 13),
                 entity_type="clearance_request", entity_id=cr.id, previous_status=prev, new_status=cr.status)
        if decide:
            who, dec, remarks, ago = decide
            prev = cr.status
            cr.status = ClearanceStatus.APPROVED if dec == "approved" else ClearanceStatus.REJECTED
            cr.decided_at = _ts(ago, 16)
            self.db.add(ApprovalDecision(clearance_request_id=cr.id, decided_by_id=self.users[who].id, decision=dec,
                                         remarks=remarks, created_at=_ts(ago, 16)))
            if dec == "approved":
                f.is_cleared = True
            _log(self.db, self.users[who], "clearance_decided",
                 f"Final decision (demo): {dec.upper()} - {remarks.rstrip('.')}. No funds are released by this system.", f,
                 _ts(ago, 16), entity_type="clearance_request", entity_id=cr.id, previous_status=prev,
                 new_status=cr.status)
        return cr

    # ---------- scenarios ----------
    def scenarios(self):
        # 1. Successfully submitted, pending document review
        f1 = self.fdr("aravalli", "SDCB", "SDCB/FDR/2025/001234", 1000000, 7.10, 160, 365, created_ago=3)
        # 2. Verified + bank confirmed, maturing in ~25 days (30-day alert)
        f2 = self.fdr("aravalli", "BSB", "BSB/FD/2025/556190", 750000, 6.90, 340, 365, created_ago=40)
        self.review(f2, "mark_checked", "Receipt, payment proof and entered details match.", 38)
        self.bank(f2, "confirmed", "Branch confirmation recorded (demo simulation).", 36, evidence=True)
        # 3. Draft, payment proof not yet uploaded (missing documents alert)
        self.fdr("aravalli", "GVDB", "GVDB/TD/2026/000318", 500000, 7.00, 5, 730, created_ago=1, submit=False,
                 payment_proof=False)

        # 4. OCR amount mismatch: entered 5 lakh, document reads 10 lakh
        self.fdr("godavari", "BSB", "BSB/FD/2025/778812", 500000, 7.25, 90, 1095, doc_principal=1000000, created_ago=4)
        # 5. Duplicate FDR number (same as #1, same bank)
        f5 = self.fdr("godavari", "SDCB", "SDCB/FDR/2025/001234", 1000000, 7.10, 150, 365, created_ago=6)
        self.review(f5, "mark_discrepancy", "FDR number already registered to another institution. Holding for bank check.", 5)
        # 6. Correction requested
        f6 = self.fdr("godavari", "DFB", "DFB/FDR/2025/090077", 600000, 6.75, 200, 1095, created_ago=12)
        self.review(f6, "request_correction", "Maturity date on the receipt is unclear; please upload a clearer scan.", 10)

        # 7. Document checked, bank verification pending
        f7 = self.fdr("narmada", "GVDB", "GVDB/TD/2025/004471", 800000, 7.40, 120, 1095, created_ago=15)
        self.review(f7, "mark_checked", "Documents in order.", 13, by="officer2")
        self.bank(f7, "pending", "Confirmation request sent to branch (demo simulation).", 12, by="officer2")
        # 8. Simulated bank mismatch
        f8 = self.fdr("narmada", "DFB", "DFB/FDR/2025/031552", 1200000, 7.00, 210, 730, created_ago=25)
        self.review(f8, "mark_checked", "Documents appear consistent.", 23)
        self.bank(f8, "mismatch", "Simulated bank response shows a different principal amount.", 20)
        # 9. 60-day alert window, verified
        f9 = self.fdr("narmada", "SDCB", "SDCB/FDR/2024/118820", 900000, 6.80, 675, 730, created_ago=50)
        self.review(f9, "mark_checked", "Verified.", 48)
        self.bank(f9, "confirmed", "Confirmed (demo simulation).", 46)

        # 10. Maturing within 7 days, verified
        f10 = self.fdr("konark", "BSB", "BSB/FD/2024/201145", 1500000, 7.20, 360, 365, created_ago=60)
        self.review(f10, "mark_checked", "Verified.", 58)
        self.bank(f10, "confirmed", "Confirmed (demo simulation).", 57, evidence=True)
        # 11. Matured; clearance requested, awaiting officer review
        f11 = self.fdr("konark", "GVDB", "GVDB/TD/2024/007781", 1000000, 6.95, 385, 365, created_ago=90)
        self.review(f11, "mark_checked", "Verified.", 88)
        self.bank(f11, "confirmed", "Confirmed (demo simulation).", 86)
        self.clearance(f11, "FDR has matured and the course approval has been completed. Requesting release clearance.", 2)
        # 12. Clearance rejected by a senior after an officer recommended rejection
        f12 = self.fdr("konark", "DFB", "DFB/FDR/2024/044320", 400000, 6.50, 400, 365, created_ago=120)
        self.review(f12, "mark_checked", "Verified.", 118, by="officer2")
        self.bank(f12, "confirmed", "Confirmed (demo simulation).", 116, by="officer2")
        self.clearance(f12, "Requesting clearance for closure of the programme.", 15,
                       recommend=("officer2", "reject", "Programme closure NOC not yet issued; clearance premature.", 12),
                       decide=("senior2", "rejected", "Agree with the officer. Re-apply after the closure NOC is issued.", 10))

        # 13. Clearance recommended, awaiting senior approval
        f13 = self.fdr("brahmaputra", "SDCB", "SDCB/FDR/2024/076615", 1100000, 7.05, 380, 365, created_ago=100)
        self.review(f13, "mark_checked", "Verified.", 98)
        self.bank(f13, "confirmed", "Confirmed (demo simulation).", 96, evidence=True)
        self.clearance(f13, "Deposit tenure complete; requesting clearance as per approval conditions.", 4,
                       recommend=("officer", "approve", "All prerequisites met; simulated bank confirmation on file.", 2))
        # 14. Completed demo clearance
        f14 = self.fdr("brahmaputra", "BSB", "BSB/FD/2024/011902", 700000, 6.60, 420, 365, created_ago=130)
        self.review(f14, "mark_checked", "Verified.", 128)
        self.bank(f14, "confirmed", "Confirmed (demo simulation).", 126)
        self.clearance(f14, "FDR matured; requesting clearance.", 30,
                       recommend=("officer", "approve", "Prerequisites satisfied.", 27),
                       decide=("senior", "approved", "Approved for demo clearance after review of all evidence.", 25))

        # Re-run validation so every record shows its current checks (e.g. both sides of the duplicate)
        for f in self.db.query(FDRRecord).all():
            run_validation(self.db, f)


def write_sample_documents(out_dir: Path) -> list[Path]:
    """Files judges can upload during the live demo."""
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today()
    issue, maturity = today - timedelta(days=20), today - timedelta(days=20) + timedelta(days=365)
    bank, branch = BANKS["SDCB"]
    holder = "Aravalli Institute of Technology"
    demo = fdr_receipt_pdf(bank=bank, branch=branch, fdr_number=LIVE_DEMO_FDR_NUMBER, institution=holder,
                           holder=holder, account_masked="XXXXXX4821", principal=1000000, rate=7.25,
                           issue=issue, maturity=maturity)
    files = {
        "SAMPLE_FDR_Aravalli_10_Lakh.pdf": demo,
        "SAMPLE_FDR_Aravalli_10_Lakh_scan.png": pdf_to_scanned_png(demo),
        "SAMPLE_Payment_Proof_Aravalli.pdf": payment_proof_pdf(bank=bank, institution=holder,
                                                               fdr_number=LIVE_DEMO_FDR_NUMBER, principal=1000000,
                                                               paid_on=issue, txn="NEFT2026DEMO4821"),
        "SAMPLE_FDR_Duplicate_Number.pdf": fdr_receipt_pdf(
            bank=bank, branch=branch, fdr_number="SDCB/FDR/2025/001234", institution=holder, holder=holder,
            account_masked="XXXXXX1234", principal=1000000, rate=7.10, issue=today - timedelta(days=160),
            maturity=today + timedelta(days=205)),
        "SAMPLE_Simulated_Bank_Letter.pdf": simulated_bank_letter_pdf(
            bank=bank, fdr_number=LIVE_DEMO_FDR_NUMBER, institution=holder, principal=1000000, on=today),
    }
    # Judge Demonstration Mode files (see JUDGE_DEMO.md)
    j1, j2 = JUDGE_DEMO1, JUDGE_DEMO2
    j1_issue = today - timedelta(days=j1["issue_ago"])
    judge1 = fdr_receipt_pdf(bank=bank, branch=branch, fdr_number=j1["number"], institution=holder, holder=holder,
                             account_masked="XXXXXX5120", principal=j1["principal"], rate=j1["rate"], issue=j1_issue,
                             maturity=j1_issue + timedelta(days=j1["tenure"]))
    gv_bank, gv_branch = BANKS["GVDB"]
    j2_issue = today - timedelta(days=j2["issue_ago"])
    judge2 = term_deposit_advice_pdf(bank=gv_bank, branch=gv_branch, receipt_no=j2["number"], institution=holder,
                                     principal=j2["principal"], rate=j2["rate"], issue=j2_issue,
                                     maturity=j2_issue + timedelta(days=j2["tenure"]), customer_id=j2["customer_id"],
                                     account_masked="XXXXXX7352", amount_words=j2["words"])
    files.update({
        "JUDGE_DEMO1_FDR_Sahyadri_10_Lakh.pdf": judge1,
        "JUDGE_DEMO1_FDR_Phone_Photo.jpg": pdf_to_phone_photo_jpg(judge1),
        "JUDGE_DEMO1_Payment_Proof.pdf": payment_proof_pdf(bank=bank, institution=holder, fdr_number=j1["number"],
                                                           principal=j1["principal"], paid_on=j1_issue,
                                                           txn="NEFT2026JUDGE5120"),
        "JUDGE_DEMO2_FDR_Ganga_Valley_7.5_Lakh.pdf": judge2,
        "JUDGE_DEMO2_Payment_Proof.pdf": payment_proof_pdf(bank=gv_bank, institution=holder, fdr_number=j2["number"],
                                                           principal=j2["principal"], paid_on=j2_issue,
                                                           txn="NEFT2026JUDGE7352"),
    })
    paths = []
    for name, data in files.items():
        p = out_dir / name
        p.write_bytes(data)
        paths.append(p)
    return paths


def backup_database(keep: int = 5) -> str | None:
    """Copy the SQLite file to data/backups before a reset (keeps the newest `keep` backups)."""
    import shutil
    if engine.dialect.name != "sqlite" or not engine.url.database:
        return None
    src = Path(engine.url.database).resolve()
    if not src.exists() or src.stat().st_size == 0:
        return None
    dest_dir = src.parent / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"surakshafd-before-reset-{datetime.now():%Y%m%d-%H%M%S}.db"
    shutil.copy2(src, dest)
    for old in sorted(dest_dir.glob("surakshafd-before-reset-*.db"))[:-keep]:
        old.unlink()
    return str(dest)


def reset_demo(backup: bool = True) -> dict:
    backup_path = backup_database() if backup else None
    drop_all(engine)
    create_all(engine)
    root = storage.storage_root()
    for p in root.glob("*"):
        if p.is_file():
            p.unlink()
    with SessionLocal() as db:
        s = Seeder(db)
        s.people()
        s.scenarios()
        db.commit()
        alerts = run_alerts(db)
    samples = write_sample_documents(Path(settings.samples_dir))
    return {"institutions": len(INSTITUTIONS), "users": len(INSTITUTIONS) + len(STAFF), "fdrs": 14,
            "alerts": alerts, "samples": [p.name for p in samples], "backup": backup_path}
