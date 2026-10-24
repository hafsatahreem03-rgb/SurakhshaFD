"""Prints what OCR extracts from each judge sample and how many fields match the known truth."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")
from app.seed import JUDGE_DEMO1 as J1, JUDGE_DEMO2 as J2  # noqa: E402
from app.services.ocr import run_ocr  # noqa: E402

S = Path(__file__).resolve().parent.parent / "sample_documents"
today = date.today()
i1, i2 = today - timedelta(days=J1["issue_ago"]), today - timedelta(days=J2["issue_ago"])
truth = {
    "JUDGE_DEMO1_FDR_Sahyadri_10_Lakh.pdf": dict(bank_name="Sahyadri Demo Co-operative Bank", branch_name="Pune Camp Branch",
        fdr_number=J1["number"], account_holder="Aravalli Institute of Technology", institution_name="Aravalli Institute of Technology",
        principal_amount="1000000.00", issue_date=i1.isoformat(), maturity_date=(i1 + timedelta(days=J1["tenure"])).isoformat(), interest_rate="7.30"),
    "JUDGE_DEMO2_FDR_Ganga_Valley_7.5_Lakh.pdf": dict(bank_name="Ganga Valley Demo Bank", branch_name="Civil Lines Branch",
        fdr_number=J2["number"], account_holder="Aravalli Institute of Technology", institution_name="Aravalli Institute of Technology",
        principal_amount="750000.00", issue_date=i2.isoformat(), maturity_date=(i2 + timedelta(days=J2["tenure"])).isoformat(), interest_rate="7.10"),
}
truth["JUDGE_DEMO1_FDR_Phone_Photo.jpg"] = truth["JUDGE_DEMO1_FDR_Sahyadri_10_Lakh.pdf"]
total_ok = total = 0
for name, t in truth.items():
    ctype = "application/pdf" if name.endswith(".pdf") else "image/jpeg"
    r = run_ocr((S / name).read_bytes(), ctype)
    ok = 0
    print(f"\n{name}: {r.status} {r.duration_ms} ms, mean conf {r.mean_confidence}")
    for f in r.fields:
        good = f.value == t[f.field_name]
        ok += good
        print(f"  {'OK ' if good else 'BAD'} {f.field_name:17} {str(f.value)[:45]:45} conf={f.confidence} {'review' if f.needs_review else ''}")
    print(f"  => {ok}/{len(r.fields)} correct")
    total_ok += ok; total += len(r.fields)
print(f"\nTOTAL {total_ok}/{total}")
