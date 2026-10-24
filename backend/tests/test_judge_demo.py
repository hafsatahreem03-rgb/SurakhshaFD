"""Judge Demonstration Mode: judge sample OCR, two-column label handling, evidence endpoints and isolation."""
from datetime import date, timedelta

import pytest

from app.config import settings
from app.seed import JUDGE_DEMO1, JUDGE_DEMO2
from app.services.ocr import Row, engine_status, extract_fields, run_ocr

OCR = engine_status()["available"]


def fields(result):
    return {f.field_name: f.value for f in result.fields}


@pytest.mark.skipif(not OCR, reason="Tesseract not installed")
@pytest.mark.parametrize("name,ctype,j", [
    ("JUDGE_DEMO1_FDR_Sahyadri_10_Lakh.pdf", "application/pdf", JUDGE_DEMO1),
    ("JUDGE_DEMO1_FDR_Phone_Photo.jpg", "image/jpeg", JUDGE_DEMO1),
    ("JUDGE_DEMO2_FDR_Ganga_Valley_7.5_Lakh.pdf", "application/pdf", JUDGE_DEMO2),
])
def test_judge_samples_ocr(samples_dir, name, ctype, j):
    r = run_ocr((samples_dir / name).read_bytes(), ctype)
    assert r.status == "completed"
    f = fields(r)
    issue = date.today() - timedelta(days=j["issue_ago"])
    assert f["fdr_number"] == j["number"]
    assert f["principal_amount"] == f"{j['principal']:.2f}"
    assert f["issue_date"] == issue.isoformat()
    assert f["maturity_date"] == (issue + timedelta(days=j["tenure"])).isoformat()
    assert f["account_holder"] == "Aravalli Institute of Technology"


def test_two_column_rows_are_split_at_next_label():
    rows = [Row("Name of Bank: Ganga Valley Demo Bank Branch Name: Civil Lines Branch", [95] * 11),
            Row("Receipt No.: GVDB/TD/2026/007352 Customer ID: CIF-1", [95] * 6),
            Row("Branch: Pune Camp Branch", [95] * 4)]
    f = {x.field_name: x.value for x in extract_fields(rows)}
    assert f["bank_name"] == "Ganga Valley Demo Bank"
    assert f["branch_name"] == "Civil Lines Branch"
    assert f["fdr_number"] == "GVDB/TD/2026/007352"
    # a value ending in a label word without a colon is not cut
    f2 = {x.field_name: x.value for x in extract_fields([Row("Branch: Pune Camp Branch", [95] * 4)])}
    assert f2["branch_name"] == "Pune Camp Branch"


def test_evidence_request_feed_respects_isolation(client, tokens):
    client.get("/api/fdrs", headers=tokens["officer"])
    client.get("/api/fdrs", headers=tokens["aravalli"])
    inst = client.get("/api/demo/requests", headers=tokens["aravalli"]).json()
    assert inst and all(e["email"] == "aravalli@demo.surakshafd.in" for e in inst)
    staff = client.get("/api/demo/requests", headers=tokens["officer"]).json()
    assert {"officer@demo.surakshafd.in", "aravalli@demo.surakshafd.in"} <= {e["email"] for e in staff}
    e = staff[0]
    assert {"method", "path", "status", "ms", "at", "role"} <= set(e)
    assert not any(p["path"].startswith("/api/demo/") for p in staff)  # polling is not logged


def test_evidence_db_snapshot(client, tokens):
    d = client.get("/api/demo/db", headers=tokens["officer"]).json()
    assert d["row_counts"]["fdr_records"] >= 14 and d["row_counts"]["audit_logs"] > 0
    assert d["latest_fdr_rows"] and d["latest_audit"]
    mine = client.get("/api/demo/db", headers=tokens["aravalli"]).json()
    assert all(r["institution"].startswith("Aravalli") for r in mine["latest_fdr_rows"])


def test_reset_is_admin_only_and_needs_confirmation(client, tokens):
    assert client.post("/api/demo/reset", json={"confirm": "RESET"}, headers=tokens["officer"]).status_code == 403
    assert client.post("/api/demo/reset", json={"confirm": "yes"}, headers=tokens["admin"]).status_code == 400


def test_demo_mode_off_hides_evidence(client, tokens, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)
    assert client.get("/api/demo/requests", headers=tokens["officer"]).status_code == 404
    assert client.get("/api/demo/config", headers=tokens["officer"]).json()["demo_mode"] is False
