# SurakshaFD: Smart FDR & Security Deposit Management Portal

**Smart India Hackathon 2026 · Problem Statement 26265 (Streamline of Security Deposit / FDR Portal) · Team Lynxcode**

SurakshaFD is a working prototype of one portal where technical institutions upload Fixed Deposit Receipts (FDRs) and AICTE officers review, verify, monitor and clear them, with every step recorded.

```
Institution registration → FDR upload → OCR extraction → automatic validation
  → (simulated) bank verification → deadline alerts → two-person clearance → audit history
```

> **Demonstration prototype.** This is not an official AICTE service. All institutions, banks, people and amounts are fictional.
> **Bank verification is simulated**: the app never contacts a bank. OCR and automatic checks **cannot prove an FDR is genuine**; that needs confirmation obtained independently from the issuing bank. A "clearance approval" here only records a decision. It **does not release any money**. All financial decisions stay with authorised officials.

---

## ▶ Demo video

[![SurakshaFD walkthrough video: click to watch on YouTube](https://img.youtube.com/vi/TdojHO2k8wA/maxresdefault.jpg)](https://youtu.be/TdojHO2k8wA)

**[Watch the 4½-minute walkthrough on YouTube](https://youtu.be/TdojHO2k8wA)**: the complete workflow running live on the real prototype.

| | |
|---|---|
| **Length** | 4 min 33 s · 1920×1080 · English narration with captions |
| **Shows** | All 11 workflow steps: institution login → FDR upload → real OCR extraction → automatic mismatch detection → correction & submission → AICTE officer review → simulated bank verification → dashboards & deadline alerts → clearance request → officer recommendation + separate senior approval → audit trail |
| **Data** | Fictional sample FDRs, banks and institutions. Bank verification is **simulated**, and the approval shown is a **demonstration only**: no funds are released. |
| **Narration** | AI-generated voice (offline [Piper](https://github.com/rhasspy/piper) text-to-speech, public-domain `en_US-john-medium` voice) |

---

## Contents
1. [What's inside](#1-whats-inside)
2. [Quick start on Windows (recommended)](#2-quick-start-on-windows-recommended)
3. [Demo login accounts](#3-demo-login-accounts-development-only)
4. [Check that everything works](#4-check-that-everything-works)
5. [Run with Docker (one command)](#5-run-with-docker-one-command)
6. [Run manually (step by step)](#6-run-manually-step-by-step)
7. [Tests](#7-tests)
8. [Five-minute judge demo](#8-five-minute-judge-demo)
9. [How it works](#9-how-it-works)
10. [Project structure](#10-project-structure)
11. [Security notes](#11-security-notes)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. What's inside

| Area | What it does |
|---|---|
| **4 roles** | Institution, AICTE Officer, Senior Approving Officer, Administrator. Each role has its own navigation, and the backend enforces every permission. |
| **FDR upload + real OCR** | PDF/JPG/PNG upload → **Tesseract** reads it (PyMuPDF renders PDF pages) → 9 fields extracted with per-field confidence. Low-confidence values are marked *Needs review* instead of being guessed. |
| **Editable OCR review** | The document is shown beside the pre-filled form. The raw OCR value is kept unchanged, and the institution's confirmed or corrected value is stored next to it. |
| **Automatic validation** | Missing fields, duplicate FDR numbers, invalid dates, maturity before issue, **amount mismatch vs OCR**, missing documents, demo deposit rules, other inconsistencies. Warnings never auto-reject. |
| **Simulated bank verification** | Officer records *confirmed / mismatch / pending / failed*. It is labelled **Demo / Simulated** everywhere and built behind an adapter interface so a real bank API can plug in later. |
| **Deadline alerts** | 60 / 30 / 7-day maturity alerts, matured FDRs, overdue reviews, missing documents, pending clearances. In-app notification centre with read/unread state. Background job plus a manual trigger. |
| **Clearance workflow** | Institution request → prerequisite check → officer recommendation → **different** senior officer's final decision with mandatory remarks (two-person rule). |
| **Audit trail** | Append-only log, blocked from edits both in code and by database triggers. Readable timeline on every case, plus a filterable log and CSV export. |
| **Policy engine** | Versioned rules with effective dates (fictional demo values). Every change is audited. |
| **Reports** | Charts by status, institution, maturity month, clearance and validation issue. Filters and CSV export. |

**Tech stack:** React 18 + Vite + TypeScript + Tailwind CSS + React Router + Lucide + Recharts + Axios · Python FastAPI + SQLAlchemy 2 + Pydantic 2 + JWT (python-jose) + bcrypt · SQLite (PostgreSQL-ready) · Tesseract OCR + pytesseract + PyMuPDF + Pillow · ReportLab for the sample documents · Docker Compose.

---

## 2. Quick start on Windows (recommended)

### Install these once
| Tool | Version | How |
|---|---|---|
| Python | 3.11 or newer (3.13 tested) | https://www.python.org/downloads/ (tick **"Add python.exe to PATH"**) |
| Node.js | 18 or newer (18.18 tested) | https://nodejs.org/ (LTS) |
| Tesseract OCR | 5.x | Command Prompt: `winget install UB-Mannheim.TesseractOCR` |

### Then, inside the `SurakshaFD` folder
1. Double-click **`setup.bat`**. It creates the Python environment, installs packages, writes `backend\.env` with a random secret, loads the demo data, checks OCR, and installs the frontend packages. It only needs to run once.
2. Double-click **`start.bat`**. Two windows open (backend and frontend), and the browser opens **http://localhost:5173**.
3. Click one of the demo accounts on the login page.

Before each live demo, double-click **`reset-demo.bat`** to restore the original demo data.

---

## 3. Demo login accounts (development only)

> These credentials are for local demonstration only. **Every account uses the password `Demo@123`.**

| Role | Email | Notes |
|---|---|---|
| Institution | `aravalli@demo.surakshafd.in` | Aravalli Institute of Technology (use this for the demo) |
| Institution | `godavari@`, `narmada@`, `konark@`, `brahmaputra@demo.surakshafd.in` | Other fictional institutions |
| AICTE Officer | `officer@demo.surakshafd.in` | Rahul Verma |
| AICTE Officer | `officer2@demo.surakshafd.in` | Anita Desai |
| Senior Approver | `senior@demo.surakshafd.in` | Dr. S. K. Rao |
| Senior Approver | `senior2@demo.surakshafd.in` | Meera Iyer |
| Administrator | `admin@demo.surakshafd.in` | Users, institutions, policies, reports, audit |

The login page has one-click buttons for the four main accounts.

### Seeded demo scenarios (14 fictional FDRs)
| Ref | Institution | Scenario |
|---|---|---|
| SFD-…-0001 | Aravalli | Submitted, **pending document review** (also shares its FDR number with 0005) |
| SFD-…-0002 | Aravalli | Verified + bank confirmed, **maturing in ~25 days** (30-day alert) |
| SFD-…-0003 | Aravalli | **Draft**, payment proof not uploaded yet |
| SFD-…-0004 | Godavari | **OCR amount mismatch** (entered ₹5,00,000, document says ₹10,00,000) |
| SFD-…-0005 | Godavari | **Duplicate FDR number**, marked as a discrepancy |
| SFD-…-0006 | Godavari | **Correction requested** by officer |
| SFD-…-0007 | Narmada | Document checked, **bank verification pending** (simulated) |
| SFD-…-0008 | Narmada | **Simulated bank mismatch** |
| SFD-…-0009 | Narmada | Verified, **~55 days to maturity** (60-day alert) |
| SFD-…-0010 | Konark | Verified, **5 days to maturity** (7-day alert) |
| SFD-…-0011 | Konark | **Matured**, clearance requested and awaiting officer |
| SFD-…-0012 | Konark | Clearance **rejected** by a senior |
| SFD-…-0013 | Brahmaputra | Clearance **awaiting senior approval** |
| SFD-…-0014 | Brahmaputra | **Completed demo clearance** |

Dates are relative to today, so the alerts always appear.

### Sample documents (folder `sample_documents/`, also downloadable on the Upload page)
- `SAMPLE_FDR_Aravalli_10_Lakh.pdf`: the ₹10,00,000 FDR for the live demo
- `SAMPLE_FDR_Aravalli_10_Lakh_scan.png`: the same FDR as a slightly rotated "scanned" image (OCR works on images too)
- `SAMPLE_Payment_Proof_Aravalli.pdf`: the required supporting document
- `SAMPLE_FDR_Duplicate_Number.pdf`: upload it to see duplicate detection
- `SAMPLE_Simulated_Bank_Letter.pdf`: evidence an officer can attach, clearly marked simulated

---

## 4. Check that everything works

| Part | How to check | Expected |
|---|---|---|
| **Backend** | Open http://localhost:8000/api/health | `"status":"ok"` |
| **Database** | Same page | `"database":"ok"` |
| **OCR** | Same page, or run `backend\.venv\Scripts\python -m app.cli check-ocr` inside `backend` | `"available": true` and 9 fields read from the sample FDR |
| **API docs** | http://localhost:8000/docs | Interactive Swagger UI |
| **Frontend** | http://localhost:5173 | Login page |
| **End to end** | Log in as Institution → Upload FDR → upload `SAMPLE_FDR_Aravalli_10_Lakh.pdf` | Form fills itself from OCR within a few seconds |

---

## 5. Run with Docker (one command)

Requires Docker Desktop.

```bat
docker compose up --build
```

- App: **http://localhost:8080** · API: http://localhost:8000/docs
- The backend image installs Tesseract itself and loads demo data on first start.
- Reset the demo: `docker compose exec backend python -m app.cli reset-demo --yes`
- Run alerts now: `docker compose exec backend python -m app.cli run-alerts`
- Stop: `Ctrl+C`, then `docker compose down` (add `-v` to delete the data volume too).
- For a shared deployment, set a real secret first: `set SECRET_KEY=your-long-random-value` before `docker compose up`.

---

## 6. Run manually (step by step)

**Backend** (Command Prompt):
```bat
cd SurakshaFD\backend
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env          &REM then edit SECRET_KEY in .env
.venv\Scripts\python -m app.cli reset-demo
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Frontend** (second Command Prompt):
```bat
cd SurakshaFD\frontend
npm install
npm run dev
```
Open http://localhost:5173. The Vite dev server forwards `/api` calls to port 8000, so CORS setup isn't needed.

On macOS or Linux, use `python3 -m venv .venv`, `.venv/bin/python`, and install Tesseract with `brew install tesseract` or `sudo apt install tesseract-ocr`.

### Developer commands (run inside `backend`)
| Command | What it does |
|---|---|
| `python -m app.cli reset-demo` | Back up the DB, wipe it and the uploads, reload fictional data, regenerate sample PDFs (asks to confirm; `--yes` skips) |
| `python -m app.cli inspect` | Show live row counts, latest FDRs and latest audit entries |
| `python -m app.cli run-alerts` | Run the deadline-alert job now (it also runs automatically every `ALERT_INTERVAL_MINUTES`) |
| `python -m app.cli check-ocr` | Check Tesseract and OCR the sample FDR |
| `python -m app.cli init-db` | Create tables only |

Admins and officers can also click **Run deadline check now** in the Notifications page.

---

## 7. Tests

**Backend automated tests** (29 tests, using a temporary database so your demo data is not touched):
```bat
run-tests.bat
```
or `cd backend` then `.venv\Scripts\python -m pytest -v`.

They cover authentication, password hashing, role-based permissions, institution data isolation (records and files), FDR creation, validation (missing fields, date errors, amount mismatch), duplicate detection, upload type and path checks, simulated bank verification, clearance prerequisites, the **two-person rule**, mandatory remarks, policy versioning, append-only audit (ORM and database triggers), and a **full end-to-end demo run with real OCR**.

**Judge demo end-to-end test**: `e2e\run-judge-test.bat` runs Demo 1 and Demo 2 in Edge (three tabs, three
roles), then reads the SQLite file directly to confirm every step was saved (25 checks, about 1 minute).

**Browser smoke test** (drives Microsoft Edge through the whole judge demo and saves screenshots to `e2e\screenshots`):
```bat
reset-demo.bat
start.bat
e2e\run-smoke-test.bat          &REM add --show to watch it
```

---

## 8. Five-minute judge demo

- **[Demo video on YouTube](https://youtu.be/TdojHO2k8wA)**: the full recorded walkthrough (see [Demo video](#-demo-video) above).
- **[JUDGE_DEMO.md](JUDGE_DEMO.md)**: **live Judge Demonstration Mode.** Demo 1 (real OCR + validation) and Demo 2
  (multi-role workflow in three browser tabs), plus how to show API calls, server logs and database changes as proof.
- **[DEMO_SCRIPT.md](DEMO_SCRIPT.md)**: the original single-thread 11-step walkthrough with talking points.

### Judge Demonstration Mode
- **Live Evidence** button (top bar): a drawer showing the real API requests FastAPI received, live database row
  counts and latest rows, and the newest audit entries. It refreshes every 2 s and respects data isolation (an institution
  sees only its own). Every request is also printed in the backend window and written to `backend\data\logs\api.log`.
- **Per-tab sign-in**: each browser tab keeps its own session, so institution, officer and senior can sit side by side.
- **Safe reset**: `reset-demo.bat` asks for confirmation and backs up the database to `backend\data\backups\` first.
  Admins can also reset from the Live Evidence panel by typing `RESET`.
- **`inspect-db.bat`**: prints live row counts, latest FDRs and latest audit entries straight from the database file.
- **Judge files**: `JUDGE_DEMO1_*` (PDF + phone photo) and `JUDGE_DEMO2_*` (a second bank layout) in `sample_documents\`.
- Turn it off for anything other than a local demo with `DEMO_MODE=false` in `backend\.env`.

### Walkthrough video: how it is made
The [YouTube video](https://youtu.be/TdojHO2k8wA) is generated from the real app by `e2e\make_video.py`. Nothing in it is a mock-up screen:
- Microsoft Edge runs the actual prototype (FastAPI, database, Tesseract OCR) and is recorded at 1080p.
- **Male AI narration**, about 1.25× pace: Piper voice `en_US-john-medium`, chosen with `e2e\voice_bench.py` as the
  clearest male voice by speech-recognition accuracy.
- **Captions sit in a band below the website**, so they never cover the app. Subtle zoom-ins, quiet click and keyboard
  sounds, and a brief closing card.

To regenerate it, double-click **`make-video.bat`** (about 10 minutes; the first run downloads the voice model). It writes
`video\SurakshaFD_Walkthrough.mp4` and a `.srt` subtitle file locally. The `video\` folder is not committed. Narration
and captions come from the `d.say(...)` lines in `walkthrough()`; `make_video.py --encode-only` re-edits the last recording.

---

## 9. How it works

### Status model: evidence-labelled, never merged
Each FDR has **separate** statuses so nobody confuses "uploaded" with "verified":

| Stage | Field | Values |
|---|---|---|
| Submission | `submission_status` | draft → submitted (→ correction_requested → submitted) |
| Document review | `document_status` | pending_review / discrepancy / correction_requested / document_checked / rejected |
| Bank verification | `bank_status` | not_started / pending / confirmed / mismatch / failed, **all simulated** |
| Clearance decision | `clearance_requests.status` | pending_officer_review → recommended_approval / recommended_rejection → approved / rejected |
| Actual fund release | n/a | **Outside this system**, shown greyed out in the UI |

### OCR pipeline (`backend/app/services/ocr.py`)
1. PDF pages are rendered at 300 dpi with PyMuPDF; images are opened with Pillow (EXIF-rotated, greyscaled, upscaled if small).
2. Tesseract returns every word with a confidence score. Words are regrouped into visual rows so a label and its value on the same line join up.
3. Labelled fields ("FDR No.", "Principal Amount", "Date of Maturity"…) are found with patterns. Amounts, dates and rates are parsed into standard formats.
4. Confidence is measured on the **value** words only. Below the policy threshold (70%) a field is marked *needs review*; if nothing is found it is left blank, never invented.

### Validation (`backend/app/services/validation.py`)
`error` blocks submission. `warning` is flagged for the officer and never auto-rejects. Example message: *"Amount mismatch detected. Entered ₹5,00,000 but the uploaded FDR reads ₹10,00,000. Please review the uploaded FDR and entered information."*

### Bank adapter (`backend/app/services/bank_adapter.py`)
`BankVerificationAdapter` is an abstract interface. `SimulatedBankAdapter` is the only implementation. A real integration (a bank's FD-status API, NeSL e-BG, etc.) would add a new class and set `BANK_ADAPTER` in `.env`; the workflow code doesn't change.

### Two-person approval (`backend/app/routers/clearances.py`)
The user who recommended a clearance (or requested it) gets **HTTP 403** if they try to make the final decision. The blocked attempt itself is written to the audit log. Final decisions need at least 10 characters of remarks.

### Database tables
`users`, `institutions`, `fdr_records`, `uploaded_documents`, `extracted_document_fields`, `validation_results`, `bank_verifications`, `clearance_requests`, `approval_decisions`, `notifications`, `policy_rules`, `policy_versions`, `audit_logs`, with timestamps, foreign keys and indexes. Tables are created reproducibly by `app/init_db.py`. To move to PostgreSQL, change `DATABASE_URL` (all column types are portable). For production, add Alembic migrations and a Postgres rule or trigger equivalent to the SQLite audit triggers.

---

## 10. Project structure

```
SurakshaFD/
├── setup.bat · start.bat · reset-demo.bat · run-tests.bat   Windows helpers
├── docker-compose.yml
├── README.md · DEMO_SCRIPT.md
├── SIH2026-Lynxcode.pptx                                     Idea presentation
├── sample_documents/                                         Fictional PDFs/PNG (regenerated by reset-demo)
├── backend/
│   ├── requirements.txt · Dockerfile · .env.example · pytest.ini
│   ├── app/
│   │   ├── main.py            FastAPI app, CORS, background alert loop
│   │   ├── config.py          Settings from environment / .env
│   │   ├── database.py        Engine + sessions
│   │   ├── models.py          All tables + append-only audit guard
│   │   ├── init_db.py         Table creation + audit triggers
│   │   ├── schemas.py         Request validation + response shapes
│   │   ├── security.py        bcrypt, JWT, role checks, data isolation
│   │   ├── audit.py           Audit helper
│   │   ├── seed.py            Fictional demo data
│   │   ├── sample_docs.py     Generates sample FDR / payment / bank-letter PDFs
│   │   ├── cli.py             reset-demo, run-alerts, check-ocr …
│   │   ├── routers/           auth, fdrs, clearances, reports (dashboards, audit, CSV), admin, misc
│   │   └── services/          ocr, validation, bank_adapter, alerts, notify, policy, storage, workflow
│   ├── tests/                 pytest suite
│   └── data/                  (created at runtime) SQLite DB + uploaded files
├── frontend/
│   ├── package.json · vite.config.ts · tailwind.config.js · Dockerfile · nginx.conf
│   └── src/
│       ├── App.tsx            Routes per role
│       ├── lib/               api client, auth context, formatters, types
│       ├── components/        Layout, Logo, UI kit, FDR widgets, review/bank actions
│       └── pages/             Login, shared (dashboard, cases, clearance, notifications),
│                              institution (upload), officer (OCR review, bank queue), admin (users, policies, reports, audit)
└── e2e/                       Edge browser smoke test of the judge demo
```

---

## 11. Security notes

- Passwords are hashed with **bcrypt**; JWTs are signed with `SECRET_KEY` from `.env` and expire after 8 hours.
- **Every API endpoint** checks the role on the server; the frontend guards only hide navigation.
- Institutions can only read their own records and files. Other institutions' IDs return 404 (not 403), so IDs aren't confirmed to exist.
- Uploads: only PDF, JPG and PNG up to 10 MB, **magic bytes must match** the extension, files are saved under random names, and paths are resolved and checked to stay inside the storage folder (no path traversal). Downloads go through an authorised endpoint, never a public folder.
- Only the last 4 digits of account numbers are stored. Document text is never written to logs or audit details.
- The audit log is append-only: the ORM refuses updates/deletes, and SQLite triggers abort any `UPDATE`/`DELETE`.
- **This is prototype-grade, not certified banking software.** Before real use you would add HTTPS, rate limiting and lockout, refresh tokens, Alembic migrations, encrypted storage, malware scanning, DPDP-compliant retention, and a real bank-confirmation channel.

---

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| `pip` fails with **SSL: CERTIFICATE_VERIFY_FAILED** | Antivirus or a proxy is intercepting HTTPS. Use Python 3.13 (its pip uses the Windows certificate store), or run `python -m pip install --use-feature=truststore -r requirements.txt`. |
| Health shows `"ocr": {"available": false}` | Install Tesseract (`winget install UB-Mannheim.TesseractOCR`), or set `TESSERACT_CMD=C:\path\to\tesseract.exe` in `backend\.env`, then restart the backend. |
| Login page says "Cannot reach the SurakshaFD server" | The backend window isn't running. Start it with `start.bat`, or check that port 8000 is free. |
| Port 5173 or 8000 already in use | Close the old server windows, or restart the PC. |
| PDF preview is blank | Use the **Download** button. Some browsers block inline PDFs; images always preview. |
| Want a fresh demo | `reset-demo.bat`, then sign in again. |
