"""Runs last: a real demo reset through the API restores seeded data and writes a backup first."""
from pathlib import Path


def test_admin_reset_restores_demo_data(client, tokens):
    client.post("/api/fdrs", json={"bank_name": "Temp"}, headers=tokens["aravalli"])
    r = client.post("/api/demo/reset", json={"confirm": "RESET"}, headers=tokens["admin"])
    assert r.status_code == 200, r.text
    assert r.json()["backup"] and Path(r.json()["backup"]).exists()
    d = client.get("/api/demo/db", headers=tokens["admin"]).json()
    assert d["row_counts"]["fdr_records"] == 14
    assert d["latest_audit"][0]["action"] == "demo_reset"
    # existing sessions keep working after a reset (users are re-created with the same ids)
    assert client.get("/api/auth/me", headers=tokens["officer"]).status_code == 200
