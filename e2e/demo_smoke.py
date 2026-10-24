"""Browser smoke test: runs the 11-step SIH judge demo in Microsoft Edge and saves screenshots.

Prerequisites: backend on :8000 and frontend on :5173 are running, demo data freshly reset.
    .venv\\Scripts\\python demo_smoke.py            (headless)
    .venv\\Scripts\\python demo_smoke.py --show     (watch it run)
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = "http://localhost:5173"
ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT.parent / "sample_documents"
SHOTS = ROOT / "screenshots"
SHOTS.mkdir(exist_ok=True)
sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252


def shot(page: Page, name: str):
    page.wait_for_timeout(600)  # let charts/animations settle
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)
    print(f"  screenshot: {name}.png")


def login(page: Page, role_button: str):
    page.goto(f"{BASE}/login")
    page.get_by_role("button", name=re.compile(role_button)).click()
    page.wait_for_url(re.compile(r"/(institution|officer|senior|admin)$"))


def logout(page: Page):
    page.get_by_role("button", name="Sign out").first.click()
    page.wait_for_url(re.compile("/login"))


def step(n, text):
    print(f"Step {n}: {text}")


def run(show: bool):
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=not show, slow_mo=150 if show else 0)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: print("  PAGE ERROR:", e))

        page.goto(f"{BASE}/login")
        shot(page, "01_login")

        step(1, "Institution logs in")
        login(page, "Institution")
        expect(page.get_by_text("Institution Dashboard")).to_be_visible()
        shot(page, "02_institution_dashboard")

        step(2, "Upload the sample ₹10,00,000 FDR")
        page.goto(f"{BASE}/institution/upload")
        page.locator("input[type=file]").first.set_input_files(str(SAMPLES / "SAMPLE_FDR_Aravalli_10_Lakh.pdf"))
        step(3, "OCR extracts bank, FDR number, amount, maturity date")
        expect(page.get_by_text("Review OCR results and deposit details")).to_be_visible(timeout=60000)
        page.wait_for_url(re.compile(r"/institution/upload/\d+"))
        fdr_id = int(page.url.rsplit("/", 1)[1])
        amount = page.locator("input[type=number]").first
        expect(amount).to_have_value("1000000.00")
        shot(page, "03_ocr_extracted")

        step(4, "Enter a different amount -> discrepancy highlighted")
        amount.fill("500000")
        expect(page.get_by_text("Amount mismatch detected").first).to_be_visible()
        page.locator("select").first.select_option("payment_proof")
        page.locator("input[type=file]").nth(1).set_input_files(str(SAMPLES / "SAMPLE_Payment_Proof_Aravalli.pdf"))
        expect(page.get_by_text("Payment proof uploaded.")).to_be_visible(timeout=20000)
        page.get_by_role("button", name="Run checks").click()
        expect(page.get_by_text("Validation:").first).to_be_visible(timeout=20000)
        shot(page, "04_amount_mismatch")

        step(5, "Correct the amount and submit")
        page.get_by_role("button", name="Use document value").first.click()
        expect(page.get_by_text("Amount mismatch detected")).to_have_count(0)
        page.get_by_role("button", name="Submit for review").click()
        page.wait_for_url(re.compile(rf"/institution/fdrs/{fdr_id}"), timeout=20000)
        shot(page, "05_submitted")
        logout(page)

        step(6, "Officer reviews the record")
        login(page, "AICTE Officer")
        shot(page, "06_officer_dashboard")
        page.goto(f"{BASE}/officer/cases/{fdr_id}/ocr")
        expect(page.get_by_text("OCR reading vs submitted record")).to_be_visible()
        shot(page, "06b_ocr_review")
        page.get_by_role("button", name="Mark documents checked").click()
        page.locator("textarea").fill("Receipt, payment proof and entered details are consistent.")
        page.get_by_role("button", name="Confirm").click()
        expect(page.get_by_text("Review recorded")).to_be_visible()

        step(7, "Simulated bank confirmation")
        page.goto(f"{BASE}/officer/cases/{fdr_id}?tab=bank")
        page.get_by_role("button", name="Bank confirmation received").click()
        page.locator("textarea").fill("Branch confirmed FDR status (demo simulation).")
        page.get_by_role("button", name=re.compile("Record simulated outcome")).click()
        expect(page.get_by_text(re.compile("Simulated outcome .confirmed. recorded"))).to_be_visible()
        shot(page, "07_bank_simulated")

        step(8, "Dashboard shows status and maturity reminders")
        page.goto(f"{BASE}/officer")
        shot(page, "08_officer_dashboard_after")
        page.goto(f"{BASE}/officer/bank")
        shot(page, "08b_bank_queue")
        logout(page)

        step(9, "Institution requests clearance; officer recommends")
        login(page, "Institution")
        page.goto(f"{BASE}/institution/fdrs/{fdr_id}?tab=clearance")
        page.locator("textarea").fill("Approval conditions completed; requesting clearance of the security deposit.")
        page.get_by_role("button", name="Submit clearance request").click()
        expect(page.get_by_text("Clearance request submitted")).to_be_visible()
        shot(page, "09_clearance_requested")
        logout(page)
        login(page, "AICTE Officer")
        page.goto(f"{BASE}/officer/cases/{fdr_id}?tab=clearance")
        page.get_by_role("link", name="Review request").click()
        page.get_by_role("button", name="Recommend approval").click()
        page.locator("textarea").fill("All prerequisites met; simulated bank confirmation on file.")
        page.get_by_role("button", name="Submit recommendation").click()
        expect(page.get_by_text("Recommendation sent")).to_be_visible()
        shot(page, "09b_officer_recommended")
        logout(page)

        step(10, "Different senior approver records the final decision")
        login(page, "Senior Approver")
        shot(page, "10_senior_dashboard")
        page.goto(f"{BASE}/senior/approvals")
        shot(page, "10b_pending_approvals")
        page.goto(f"{BASE}/senior/cases/{fdr_id}?tab=clearance")
        page.get_by_role("link", name="Record decision").click()
        page.get_by_role("button", name="Approve", exact=True).click()
        page.locator("textarea").fill("Reviewed all evidence; approved for demo clearance.")
        page.get_by_role("button", name="Record final decision").click()
        expect(page.get_by_text(re.compile("Final decision recorded"))).to_be_visible()
        shot(page, "10c_decision_recorded")

        step(11, "Audit timeline proves every action")
        page.goto(f"{BASE}/senior/cases/{fdr_id}?tab=audit")
        for action in ["OCR completed", "FDR submitted", "Bank verification simulated", "Clearance decided"]:
            expect(page.get_by_text(action, exact=True).first).to_be_visible()
        shot(page, "11_audit_timeline")
        logout(page)

        print("Extra pages")
        login(page, "Administrator")
        shot(page, "12_admin_dashboard")
        for path, name in [("reports", "13_reports"), ("policies", "14_policies"), ("audit", "15_audit_logs"),
                           ("users", "16_users"), ("notifications", "17_notifications")]:
            page.goto(f"{BASE}/admin/{path}")
            page.wait_for_load_state("networkidle")
            shot(page, name)
        logout(page)

        mobile = browser.new_page(viewport={"width": 390, "height": 844})
        login(mobile, "Institution")
        shot(mobile, "18_mobile_dashboard")
        mobile.goto(f"{BASE}/institution/fdrs/{fdr_id}")
        shot(mobile, "19_mobile_detail")
        browser.close()
        print(f"\nDEMO SMOKE TEST PASSED - screenshots in {SHOTS}")


if __name__ == "__main__":
    run("--show" in sys.argv)
