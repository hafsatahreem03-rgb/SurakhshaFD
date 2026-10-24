"""End-to-end verification of both Judge Demonstration Mode demos, in Microsoft Edge.

    .venv\\Scripts\\python judge_demo_test.py           (headless)
    .venv\\Scripts\\python judge_demo_test.py --show    (watch it)

Resets the demo data, starts the servers if needed, runs DEMO 1 (real OCR + validation, using the phone photo)
and DEMO 2 (multi-role workflow with institution / officer / senior in separate tabs), then reads the SQLite
file directly to prove every result was persisted, and checks the API log file.
"""
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

from make_video import BACKEND, PY, ROOT, SAMPLES, ensure_servers, stop_ports  # noqa: F401 (sets browser path)

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://localhost:5173"
DB = BACKEND / "data" / "surakshafd.db"
API_LOG = BACKEND / "data" / "logs" / "api.log"
SHOTS = Path(__file__).resolve().parent / "screenshots" / "judge"
SHOTS.mkdir(parents=True, exist_ok=True)
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = ""):
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{' - ' + detail if detail else ''}")
    if not ok:
        raise AssertionError(f"{name}: {detail}")


def db_rows(sql: str, *args):
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)  # read-only: proves what is on disk
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def login(page: Page, label: str):
    page.goto(f"{BASE}/login")
    page.get_by_role("button", name=re.compile(label)).click()
    page.wait_for_url(re.compile(r"/(institution|officer|senior|admin)$"))


def upload_and_submit(page: Page, fdr_file: str, proof_file: str, wrong_amount: str | None, expect_amount: str) -> int:
    page.goto(f"{BASE}/institution/upload")
    page.locator("input[type=file]").first.set_input_files(str(SAMPLES / fdr_file))
    expect(page.get_by_text("Running Tesseract OCR")).to_be_visible(timeout=5000)  # loading state shown
    expect(page.get_by_text("Review OCR results and deposit details")).to_be_visible(timeout=60000)
    page.wait_for_url(re.compile(r"/institution/upload/\d+"))
    fdr_id = int(page.url.rsplit("/", 1)[1])
    amount = page.locator("input[type=number]").first
    expect(amount).to_have_value(expect_amount)
    check(f"OCR pre-filled principal from {fdr_file}", True, expect_amount)
    if wrong_amount:
        amount.fill(wrong_amount)
        expect(page.get_by_text("Amount mismatch detected").first).to_be_visible()
        check("Live amount-mismatch warning shown", True)
    page.locator("select").first.select_option("payment_proof")
    page.locator("input[type=file]").nth(1).set_input_files(str(SAMPLES / proof_file))
    expect(page.get_by_text("Payment proof uploaded.")).to_be_visible(timeout=20000)
    page.get_by_role("button", name="Run checks").click()
    expect(page.get_by_text("Validation:").first).to_be_visible(timeout=20000)
    if wrong_amount:
        expect(page.get_by_text(re.compile("Amount mismatch detected. Entered ₹5,00,000"))).to_be_visible()
        check("Backend validation returned AMOUNT_MISMATCH warning", True)
        page.screenshot(path=str(SHOTS / "demo1_mismatch.png"), full_page=True)
        page.get_by_role("button", name="Use document value").first.click()
        expect(page.get_by_text("Amount mismatch detected")).to_have_count(0)
        check("Mismatch cleared after correction", True)
    page.get_by_role("button", name="Submit for review").click()
    page.wait_for_url(re.compile(rf"/institution/fdrs/{fdr_id}"), timeout=20000)
    return fdr_id


def run(show: bool):
    print("Resetting demo data…")
    subprocess.run([PY, "-m", "app.cli", "reset-demo", "--yes"], cwd=BACKEND, check=True, stdout=subprocess.DEVNULL)
    started = ensure_servers()
    t_start = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=not show, slow_mo=120 if show else 0)
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            errors: list[str] = []
            inst, off, sen = ctx.new_page(), ctx.new_page(), ctx.new_page()  # three TABS of one browser window
            for p in (inst, off, sen):
                p.on("pageerror", lambda e: errors.append(str(e)))

            print("\nSetup: three tabs, three roles")
            login(inst, "Institution"); login(off, "AICTE Officer"); login(sen, "Senior Approver")
            inst.reload()
            expect(inst.get_by_text("Institution Dashboard")).to_be_visible()
            check("Per-tab sessions: institution tab still institution after officer/senior signed in", True)

            # ---------------- DEMO 1 ----------------
            print("\nDEMO 1: real OCR + validation (phone photo)")
            d1 = upload_and_submit(inst, "JUDGE_DEMO1_FDR_Phone_Photo.jpg", "JUDGE_DEMO1_Payment_Proof.pdf",
                                   wrong_amount="500000", expect_amount="1000000.00")
            inst.screenshot(path=str(SHOTS / "demo1_submitted.png"), full_page=True)
            row = db_rows("SELECT reference_no, principal_amount, submission_status, document_status FROM fdr_records WHERE id=?", d1)[0]
            check("DB: Demo 1 FDR persisted as submitted with corrected amount",
                  row[1] == 1000000 and row[2] == "submitted" and row[3] == "pending_review", str(row))
            n_fields = db_rows("SELECT COUNT(*) FROM extracted_document_fields WHERE fdr_id=? AND extracted_value IS NOT NULL", d1)[0][0]
            check("DB: OCR values stored (raw, unedited)", n_fields == 9, f"{n_fields}/9 fields")
            vr = db_rows("SELECT DISTINCT check_code, severity FROM validation_results WHERE fdr_id=?", d1)
            check("DB: validation history keeps the AMOUNT_MISMATCH warning and the later pass",
                  ("AMOUNT_MISMATCH", "warning") in vr and ("AMOUNT_MISMATCH", "pass") in vr)
            ocr_doc = db_rows("SELECT ocr_status, ocr_engine, content_type FROM uploaded_documents WHERE fdr_id=? AND doc_type='fdr_receipt'", d1)[0]
            check("DB: document OCR'd by Tesseract", ocr_doc[0] == "completed" and "tesseract" in ocr_doc[1], str(ocr_doc))

            # ---------------- DEMO 2 ----------------
            print("\nDEMO 2: live multi-role workflow")
            d2 = upload_and_submit(inst, "JUDGE_DEMO2_FDR_Ganga_Valley_7.5_Lakh.pdf", "JUDGE_DEMO2_Payment_Proof.pdf",
                                   wrong_amount=None, expect_amount="750000.00")
            ref2 = db_rows("SELECT reference_no FROM fdr_records WHERE id=?", d2)[0][0]
            check("Institution submitted Demo 2 FDR", True, ref2)

            off.goto(f"{BASE}/officer")
            latest = off.get_by_text("Latest submissions").locator("xpath=ancestor::section")
            expect(latest.get_by_text(ref2)).to_be_visible()
            check("Officer dashboard shows the new submission", True)
            off.screenshot(path=str(SHOTS / "demo2_officer_dashboard.png"), full_page=True)
            latest.get_by_text(ref2).click()
            off.get_by_role("link", name="OCR review").click()
            expect(off.get_by_text("No differences")).to_be_visible()
            off.get_by_role("button", name="Mark documents checked").click()
            off.locator("textarea").fill("Term deposit advice and payment proof are consistent.")
            off.get_by_role("button", name="Confirm").click()
            expect(off.get_by_text("Review recorded")).to_be_visible()
            off.goto(f"{BASE}/officer/cases/{d2}?tab=bank")
            expect(off.get_by_text("This prototype does not contact any bank")).to_be_visible()
            off.get_by_role("button", name="Bank confirmation received").click()
            off.locator("textarea").fill("Branch confirmation (demo simulation).")
            off.get_by_role("button", name=re.compile("Record simulated outcome")).click()
            expect(off.get_by_text(re.compile("Simulated outcome .confirmed. recorded"))).to_be_visible()
            expect(off.get_by_text("Demo / Simulated").first).to_be_visible()
            check("Officer review + SIMULATED bank verification via API", True)

            inst.goto(f"{BASE}/institution/fdrs/{d2}?tab=clearance")
            expect(inst.get_by_text("Bank verification confirmed (simulated in demo)")).to_be_visible()
            inst.locator("textarea").fill("Approval conditions completed; requesting clearance of the security deposit.")
            inst.get_by_role("button", name="Submit clearance request").click()
            expect(inst.get_by_text("Clearance request submitted")).to_be_visible()
            check("Institution submitted eligible clearance request", True)

            off.goto(f"{BASE}/officer/cases/{d2}?tab=clearance")
            off.get_by_role("link", name="Review request").click()
            off.get_by_role("button", name="Recommend approval").click()
            off.locator("textarea").fill("All prerequisites met; simulated bank confirmation on file.")
            off.get_by_role("button", name="Submit recommendation").click()
            expect(off.get_by_text("Recommendation sent")).to_be_visible()
            check("Officer recommended approval", True)

            sen.goto(f"{BASE}/senior/cases/{d2}?tab=clearance")
            sen.get_by_role("link", name="Record decision").click()
            sen.get_by_role("button", name="Approve", exact=True).click()
            sen.locator("textarea").fill("Reviewed all evidence; approved for demo clearance.")
            sen.get_by_role("button", name="Record final decision").click()
            expect(sen.get_by_text(re.compile("Final decision recorded"))).to_be_visible()
            check("Different senior officer recorded final approval", True)

            sen.goto(f"{BASE}/senior/cases/{d2}?tab=audit")
            for a in ["FDR created", "OCR completed", "FDR submitted", "Review mark checked", "Bank verification simulated",
                      "Clearance requested", "Clearance recommended", "Clearance decided"]:
                expect(sen.get_by_text(a, exact=True).first).to_be_visible()
            check("Audit timeline shows every step", True)
            sen.screenshot(path=str(SHOTS / "demo2_audit.png"), full_page=True)

            # ---- persisted state, read straight from the database file
            f = db_rows("SELECT submission_status, document_status, bank_status, is_cleared FROM fdr_records WHERE id=?", d2)[0]
            check("DB: Demo 2 FDR is document_checked, bank confirmed, cleared",
                  f == ("submitted", "document_checked", "confirmed", 1), str(f))
            bv = db_rows("SELECT outcome, is_simulated, adapter, reference FROM bank_verifications WHERE fdr_id=?", d2)[0]
            check("DB: bank verification stored as SIMULATED", bv[1] == 1 and bv[2] == "simulated-demo", str(bv))
            cr = db_rows("""SELECT c.status, r.email, d.decision, s.email FROM clearance_requests c
                            JOIN users r ON r.id=c.recommended_by_id JOIN approval_decisions d ON d.clearance_request_id=c.id
                            JOIN users s ON s.id=d.decided_by_id WHERE c.fdr_id=?""", d2)[0]
            check("DB: two-person approval (recommender != approver)", cr[0] == "approved" and cr[1] != cr[3], str(cr))
            audit = db_rows("SELECT action, created_at, user_email FROM audit_logs WHERE fdr_id=? ORDER BY id", d2)
            times = [a[1] for a in audit]
            check("DB: audit entries timestamped in order, by 3 different users",
                  times == sorted(times) and len({a[2] for a in audit}) == 3 and times[0] >= t_start.isoformat(" "),
                  f"{len(audit)} entries, {times[0]} → {times[-1]}")

            # ---- execution evidence panel + API log
            off.goto(f"{BASE}/officer/cases/{d2}")
            off.get_by_test_id("evidence-button").click()
            expect(off.get_by_role("dialog", name="Live execution evidence")).to_be_visible()
            expect(off.get_by_text(f"/api/fdrs/{d2}/bank-verifications").first).to_be_visible(timeout=10000)
            check("Live Evidence panel lists the real API calls", True)
            off.screenshot(path=str(SHOTS / "evidence_api.png"))
            off.get_by_role("button", name="Database").click()
            expect(off.get_by_text("fdr_records, most recently updated")).to_be_visible()
            off.screenshot(path=str(SHOTS / "evidence_db.png"))
            off.get_by_role("button", name="Audit log").click()
            off.screenshot(path=str(SHOTS / "evidence_audit.png"))
            inst.goto(f"{BASE}/institution")
            inst.get_by_test_id("evidence-button").click()
            expect(inst.get_by_text("/api/fdrs").first).to_be_visible(timeout=10000)
            emails = set(re.findall(r"[\w.]+@demo\.surakshafd\.in", inst.get_by_role("dialog").inner_text()))
            check("Evidence panel isolation: institution sees only its own requests",
                  emails == {"aravalli@demo.surakshafd.in"}, str(emails))
            log_text = API_LOG.read_text(encoding="utf-8") if API_LOG.exists() else ""
            check("API log file records the workflow", f"POST   /api/fdrs/{d2}/bank-verifications" in log_text
                  and f"/api/clearance-requests" in log_text, str(API_LOG))
            check("No browser JavaScript errors", not errors, "; ".join(errors[:3]))
            browser.close()
    finally:
        if started:
            stop_ports(8000, 5173)
    print(f"\nALL {len(results)} CHECKS PASSED - screenshots in {SHOTS}")


if __name__ == "__main__":
    run("--show" in sys.argv)
