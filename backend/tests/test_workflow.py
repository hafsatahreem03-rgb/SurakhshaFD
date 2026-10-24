import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models import AuditLog
from app.services.ocr import engine_status

OCR_AVAILABLE = engine_status()["available"]


def find_fdr(client, headers, fdr_number):
    rows = client.get("/api/fdrs", params={"q": fdr_number}, headers=headers).json()
    return rows[0] if rows else None


# ---------------- Authentication ----------------

def test_login_success_and_me(client, tokens):
    r = client.get("/api/auth/me", headers=tokens["officer"])
    assert r.status_code == 200
    assert r.json()["role"] == "officer"


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"email": "officer@demo.surakshafd.in", "password": "wrong"})
    assert r.status_code == 401
    assert "Incorrect" in r.json()["detail"]


def test_protected_endpoint_requires_token(client):
    assert client.get("/api/fdrs").status_code == 401
    assert client.get("/api/fdrs", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_passwords_are_hashed():
    with SessionLocal() as db:
        h = db.execute(text("SELECT password_hash FROM users LIMIT 1")).scalar_one()
    assert h.startswith("$2") and "Demo@123" not in h


# ---------------- RBAC ----------------

def test_institution_cannot_use_officer_or_admin_endpoints(client, tokens):
    fdr = find_fdr(client, tokens["aravalli"], "SDCB/FDR/2025/001234")
    r = client.post(f"/api/fdrs/{fdr['id']}/review", json={"action": "mark_checked", "remarks": "self check"},
                    headers=tokens["aravalli"])
    assert r.status_code == 403
    assert client.get("/api/admin/users", headers=tokens["aravalli"]).status_code == 403
    assert client.get("/api/audit", headers=tokens["aravalli"]).status_code == 403


def test_officer_cannot_make_final_decision_or_admin_tasks(client, tokens):
    crs = client.get("/api/clearance-requests", params={"status": "awaiting_decision"}, headers=tokens["officer"]).json()
    assert crs
    r = client.post(f"/api/clearance-requests/{crs[0]['id']}/decide",
                    json={"decision": "approved", "remarks": "officer trying to approve"}, headers=tokens["officer"])
    assert r.status_code == 403
    assert client.get("/api/admin/users", headers=tokens["officer"]).status_code == 403


def test_officer_cannot_create_fdr(client, tokens):
    assert client.post("/api/fdrs", json={}, headers=tokens["officer"]).status_code == 403


# ---------------- Institution data isolation ----------------

def test_institution_sees_only_own_records(client, tokens):
    mine = client.get("/api/fdrs", headers=tokens["aravalli"]).json()
    assert mine and all(f["institution_name"].startswith("Aravalli") for f in mine)


def test_institution_cannot_open_other_institution_record_or_document(client, tokens):
    other = client.get("/api/fdrs", headers=tokens["godavari"]).json()[0]
    assert client.get(f"/api/fdrs/{other['id']}", headers=tokens["aravalli"]).status_code == 404
    detail = client.get(f"/api/fdrs/{other['id']}", headers=tokens["godavari"]).json()
    doc_id = detail["documents"][0]["id"]
    assert client.get(f"/api/documents/{doc_id}/file", headers=tokens["aravalli"]).status_code == 404
    assert client.get(f"/api/documents/{doc_id}/file", headers=tokens["godavari"]).status_code == 200


# ---------------- FDR creation, validation, duplicates ----------------

def test_create_fdr_and_missing_fields_block_submission(client, tokens):
    r = client.post("/api/fdrs", json={"bank_name": "Bharat Sample Bank"}, headers=tokens["aravalli"])
    assert r.status_code == 201
    fid = r.json()["id"]
    assert r.json()["submission_status"] == "draft"
    r = client.post(f"/api/fdrs/{fid}/submit", headers=tokens["aravalli"])
    assert r.status_code == 422
    codes = {x["check_code"] for x in r.json()["detail"]["results"] if x["severity"] == "error"}
    assert {"MISSING_FIELD", "MISSING_DOCUMENT"} <= codes


def test_maturity_before_issue_is_error(client, tokens):
    r = client.post("/api/fdrs", json={"issue_date": "2026-05-01", "maturity_date": "2026-01-01"},
                    headers=tokens["aravalli"])
    res = client.post(f"/api/fdrs/{r.json()['id']}/validate", headers=tokens["aravalli"]).json()["results"]
    assert any(x["check_code"] == "MATURITY_BEFORE_ISSUE" and x["severity"] == "error" for x in res)


def test_seeded_amount_mismatch_is_warning(client, tokens):
    fdr = find_fdr(client, tokens["godavari"], "BSB/FD/2025/778812")
    detail = client.get(f"/api/fdrs/{fdr['id']}", headers=tokens["godavari"]).json()
    mm = [x for x in detail["validation_results"] if x["check_code"] == "AMOUNT_MISMATCH"]
    assert mm and mm[0]["severity"] == "warning"
    assert "Amount mismatch detected" in mm[0]["message"]
    assert detail["submission_status"] == "submitted"  # flagged, not auto-rejected


def test_duplicate_detection(client, tokens):
    fdr = find_fdr(client, tokens["godavari"], "SDCB/FDR/2025/001234")
    detail = client.get(f"/api/fdrs/{fdr['id']}", headers=tokens["godavari"]).json()
    assert any(x["check_code"] == "DUPLICATE_FDR" and x["severity"] == "warning" for x in detail["validation_results"])


def test_upload_rejects_wrong_file_types(client, tokens):
    fid = client.post("/api/fdrs", json={}, headers=tokens["aravalli"]).json()["id"]
    r = client.post(f"/api/fdrs/{fid}/documents", data={"doc_type": "fdr_receipt"},
                    files={"file": ("evil.exe", b"MZ....", "application/octet-stream")}, headers=tokens["aravalli"])
    assert r.status_code == 400
    r = client.post(f"/api/fdrs/{fid}/documents", data={"doc_type": "fdr_receipt"},
                    files={"file": ("fake.pdf", b"not really a pdf", "application/pdf")}, headers=tokens["aravalli"])
    assert r.status_code == 400
    r = client.post(f"/api/fdrs/{fid}/documents", data={"doc_type": "fdr_receipt"},
                    files={"file": ("../../etc/passwd.png", b"\x89PNG\r\n\x1a\n" + b"0" * 10, "image/png")},
                    headers=tokens["aravalli"])
    # name is sanitised; file is stored under a random name (OCR may fail on this junk image, that's fine)
    assert r.status_code == 201
    assert r.json()["document"]["original_filename"] == "passwd.png"


# ---------------- Bank verification simulator ----------------

def test_simulated_bank_verification(client, tokens):
    fdr = find_fdr(client, tokens["officer"], "SDCB/FDR/2025/001234")
    r = client.post(f"/api/fdrs/{fdr['id']}/bank-verifications", json={"outcome": "pending", "remarks": "sent to branch"},
                    headers=tokens["officer"])
    assert r.status_code == 201
    v = r.json()
    assert v["is_simulated"] is True and v["reference"].startswith("SIM-")
    assert "SIMULATED" in v["response_summary"]
    # institution cannot simulate
    r = client.post(f"/api/fdrs/{fdr['id']}/bank-verifications", json={"outcome": "confirmed", "remarks": "x" * 5},
                    headers=tokens["aravalli"])
    assert r.status_code == 403


# ---------------- Clearance + two-person approval ----------------

def test_clearance_requires_prerequisites(client, tokens):
    fdr = find_fdr(client, tokens["aravalli"], "SDCB/FDR/2025/001234")  # not yet document-checked
    r = client.post(f"/api/fdrs/{fdr['id']}/clearance-requests", json={"reason": "please clear it"},
                    headers=tokens["aravalli"])
    assert r.status_code == 400
    assert r.json()["detail"]["unmet"]


def test_two_person_rule(client, tokens):
    crs = client.get("/api/clearance-requests", params={"status": "pending_officer_review"},
                     headers=tokens["senior"]).json()
    cr = crs[0]
    # senior2 acts as the reviewing officer...
    r = client.post(f"/api/clearance-requests/{cr['id']}/recommend",
                    json={"recommendation": "approve", "remarks": "All prerequisites met."}, headers=tokens["senior2"])
    assert r.status_code == 200
    # ...so senior2 cannot also give the final approval
    r = client.post(f"/api/clearance-requests/{cr['id']}/decide",
                    json={"decision": "approved", "remarks": "Approving my own recommendation"}, headers=tokens["senior2"])
    assert r.status_code == 403
    assert "Two-person" in r.json()["detail"]
    # remarks are mandatory
    r = client.post(f"/api/clearance-requests/{cr['id']}/decide", json={"decision": "approved", "remarks": ""},
                    headers=tokens["senior"])
    assert r.status_code == 422
    r = client.post(f"/api/clearance-requests/{cr['id']}/decide",
                    json={"decision": "approved", "remarks": "Reviewed all evidence; approved for demo."},
                    headers=tokens["senior"])
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert r.json()["fdr"]["is_cleared"] is True


# ---------------- Audit ----------------

def test_audit_records_and_is_append_only(client, tokens):
    logs = client.get("/api/audit", headers=tokens["admin"]).json()
    actions = {a["action"] for a in logs}
    assert {"login", "fdr_submitted", "bank_verification_simulated", "clearance_decided",
            "two_person_rule_blocked"} <= actions
    with SessionLocal() as db:
        entry = db.query(AuditLog).first()
        entry.description = "tampered"
        with pytest.raises(PermissionError):
            db.commit()
        db.rollback()
        with pytest.raises(Exception):
            db.execute(text("UPDATE audit_logs SET description='tampered' WHERE id=1"))
            db.commit()
        db.rollback()
        with pytest.raises(Exception):
            db.execute(text("DELETE FROM audit_logs"))
            db.commit()


def test_policy_versioning(client, tokens):
    r = client.post("/api/policies/alert_intervals/versions",
                    json={"value": {"days_before_maturity": [90, 30, 7], "review_sla_days": 5},
                          "effective_from": "2026-01-01", "change_note": "Test change"}, headers=tokens["admin"])
    assert r.status_code == 201
    assert r.json()["versions"][0]["version"] == 2
    r = client.post("/api/policies/alert_intervals/versions",
                    json={"value": {"days_before_maturity": "soon"}, "effective_from": "2026-01-01",
                          "change_note": "bad"}, headers=tokens["admin"])
    assert r.status_code == 400
    assert client.post("/api/policies/alert_intervals/versions", json={"value": {}, "effective_from": "2026-01-01",
                       "change_note": "x" * 5}, headers=tokens["officer"]).status_code == 403


# ---------------- Full live-demo scenario with real OCR ----------------

@pytest.mark.skipif(not OCR_AVAILABLE, reason="Tesseract not installed")
def test_end_to_end_demo_with_real_ocr(client, tokens, samples_dir):
    inst, off, sen = tokens["aravalli"], tokens["officer"], tokens["senior"]
    fid = client.post("/api/fdrs", json={}, headers=inst).json()["id"]
    pdf = (samples_dir / "SAMPLE_FDR_Aravalli_10_Lakh.pdf").read_bytes()
    r = client.post(f"/api/fdrs/{fid}/documents", data={"doc_type": "fdr_receipt"},
                    files={"file": ("fdr.pdf", pdf, "application/pdf")}, headers=inst)
    assert r.status_code == 201
    assert r.json()["document"]["ocr_status"] == "completed"
    fields = {f["field_name"]: f for f in r.json()["extracted_fields"]}
    assert fields["principal_amount"]["extracted_value"] == "1000000.00"
    assert fields["fdr_number"]["extracted_value"] == "SDCB/FDR/2026/004817"
    assert fields["bank_name"]["extracted_value"] == "Sahyadri Demo Co-operative Bank"

    proof = (samples_dir / "SAMPLE_Payment_Proof_Aravalli.pdf").read_bytes()
    client.post(f"/api/fdrs/{fid}/documents", data={"doc_type": "payment_proof"},
                files={"file": ("proof.pdf", proof, "application/pdf")}, headers=inst)
    body = {"fdr_number": fields["fdr_number"]["extracted_value"], "bank_name": fields["bank_name"]["extracted_value"],
            "branch_name": fields["branch_name"]["extracted_value"],
            "account_holder": fields["account_holder"]["extracted_value"],
            "principal_amount": 500000, "interest_rate": 7.25,
            "issue_date": fields["issue_date"]["extracted_value"],
            "maturity_date": fields["maturity_date"]["extracted_value"]}
    client.put(f"/api/fdrs/{fid}", json=body, headers=inst)
    res = client.post(f"/api/fdrs/{fid}/validate", headers=inst).json()["results"]
    assert any(x["check_code"] == "AMOUNT_MISMATCH" and x["severity"] == "warning" for x in res)

    body["principal_amount"] = 1000000
    client.put(f"/api/fdrs/{fid}", json=body, headers=inst)
    client.put(f"/api/fdrs/{fid}/extracted-fields",
               json={"fields": [{"id": f["id"], "confirmed_value": f["extracted_value"]} for f in fields.values()]},
               headers=inst)
    r = client.post(f"/api/fdrs/{fid}/submit", headers=inst)
    assert r.status_code == 200, r.text
    assert not any(x["check_code"] == "AMOUNT_MISMATCH" and x["severity"] == "warning" for x in r.json()["results"])

    assert client.post(f"/api/fdrs/{fid}/review", json={"action": "mark_checked", "remarks": "Documents match"},
                       headers=off).status_code == 200
    assert client.post(f"/api/fdrs/{fid}/bank-verifications", json={"outcome": "confirmed", "remarks": "Demo confirm"},
                       headers=off).status_code == 201
    r = client.post(f"/api/fdrs/{fid}/clearance-requests", json={"reason": "Tenure complete, request clearance"},
                    headers=inst)
    assert r.status_code == 201
    cr = r.json()["id"]
    assert client.post(f"/api/clearance-requests/{cr}/recommend",
                       json={"recommendation": "approve", "remarks": "All checks passed"}, headers=off).status_code == 200
    r = client.post(f"/api/clearance-requests/{cr}/decide",
                    json={"decision": "approved", "remarks": "Approved after reviewing all evidence"}, headers=sen)
    assert r.status_code == 200
    timeline = [a["action"] for a in client.get(f"/api/fdrs/{fid}/audit", headers=inst).json()]
    for a in ["fdr_created", "document_uploaded", "ocr_completed", "validation_run", "ocr_reviewed", "fdr_submitted",
              "review_mark_checked", "bank_verification_simulated", "clearance_requested", "clearance_recommended",
              "clearance_decided"]:
        assert a in timeline, a
    notes = client.get("/api/notifications", headers=inst).json()
    assert any("Clearance approved" in n["title"] for n in notes)
