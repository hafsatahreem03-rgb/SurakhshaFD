"""Tests run against a throw-away database and storage folder, seeded with the fictional demo data."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp(prefix="surakshafd-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(_tmp / "uploads")
os.environ["SAMPLES_DIR"] = str(_tmp / "samples")
os.environ["ALERT_INTERVAL_MINUTES"] = "0"
os.environ["SECRET_KEY"] = "test-secret"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seed import DEMO_PASSWORD, reset_demo  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded():
    reset_demo()
    yield


@pytest.fixture(scope="session")
def client(seeded):
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def tokens(client):
    out = {}
    for who in ["aravalli", "godavari", "officer", "officer2", "senior", "senior2", "admin"]:
        r = client.post("/api/auth/login", json={"email": f"{who}@demo.surakshafd.in", "password": DEMO_PASSWORD})
        assert r.status_code == 200, r.text
        out[who] = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return out


@pytest.fixture(scope="session")
def samples_dir():
    return Path(os.environ["SAMPLES_DIR"])
