# SurakshaFD: Judge Demonstration Mode (live, five minutes)

Two live demonstrations that run on the real FastAPI server, Tesseract OCR and the SQLite database, plus
the commands to prove it if judges ask. Nothing in either demo is a hard-coded frontend response.

> **Recorded walkthrough:** https://youtu.be/TdojHO2k8wA (4 min 33 s). Keep it open as a fallback in case the live setup fails.

> All institutions, banks and amounts are fictional. **Bank verification is SIMULATED**: no bank is contacted,
> and the UI labels it that way everywhere. A clearance approval only records a decision; it releases no money.

---

## Before the judges arrive (3 minutes)

1. **Reset the data.** Double-click `reset-demo.bat` and type `YES`. It first copies the current database to
   `backend\data\backups\`, then reloads the fictional demo data. (Admins can also reset from the
   **Live Evidence** panel. That reset asks you to type `RESET`.)
2. **Start the app.** Double-click `start.bat`. Keep the **backend window** visible on a second screen if you have one: it
   prints a line for every API request.
3. **Open three tabs** in one browser window at http://localhost:5173. Each tab signs in separately:

   | Tab | Click on the login page | Account (password `Demo@123`, development only) |
   |---|---|---|
   | 1 | **Institution** | `aravalli@demo.surakshafd.in` |
   | 2 | **AICTE Officer** | `officer@demo.surakshafd.in` |
   | 3 | **Senior Approver** | `senior@demo.surakshafd.in` |

4. **Have the judge files ready** in `sample_documents\` (also downloadable from the Upload page):

   | File | Used in | What OCR should read |
   |---|---|---|
   | `JUDGE_DEMO1_FDR_Sahyadri_10_Lakh.pdf` | Demo 1 | SDCB/FDR/2026/005120, ₹10,00,000 |
   | `JUDGE_DEMO1_FDR_Phone_Photo.jpg` | Demo 1 (photo alternative) | same FDR, photographed at an angle |
   | `JUDGE_DEMO1_Payment_Proof.pdf` | Demo 1 | supporting document |
   | `JUDGE_DEMO2_FDR_Ganga_Valley_7.5_Lakh.pdf` | Demo 2 | GVDB/TD/2026/007352, ₹7,50,000 (different two-column layout) |
   | `JUDGE_DEMO2_Payment_Proof.pdf` | Demo 2 | supporting document |

   Each demo FDR number is unused in the seeded data, so neither triggers a duplicate warning.
   **Run each demo once per reset.** A second upload of the same FDR is correctly flagged as a duplicate.

---

## DEMO 1: Real OCR + validation (about 2 minutes) · Tab 1, Institution

| Do | Say |
|---|---|
| **Upload FDR** → drop `JUDGE_DEMO1_FDR_Sahyadri_10_Lakh.pdf` (or the phone photo) | "This is a brand-new fictional FDR. Watch: *Running Tesseract OCR*. That's the real engine on our server." |
| The form fills in about 1–2 s; point at the confidence badges | "Bank, FDR number, ₹10,00,000, issue and maturity dates, each with a confidence score. Anything below 70% is marked *Needs review*, never trusted blindly. The original document is right beside it." |
| Click **Principal amount**, type `500000` | "Suppose the clerk types ₹5 lakh…" The field turns red and **Amount mismatch detected** appears. |
| Step 3: upload `JUDGE_DEMO1_Payment_Proof.pdf`, then **Run checks** | "The backend validation also returns a mismatch **warning**. It's flagged for an officer, never auto-rejected, because OCR can be wrong." |
| **Use document value**, then **Submit for review** | "Corrected and submitted. It's now saved in the database." |
| Click **Live Evidence** (top bar), then the **Database** tab | "Here's the new `fdr_records` row and the row counts that just went up: uploaded documents, 9 extracted fields, validation results, audit entries." |

## DEMO 2: Live multi-role workflow (about 3 minutes)

| Tab | Do | Say |
|---|---|---|
| 1 Institution | **Upload FDR** → `JUDGE_DEMO2_FDR_Ganga_Valley_7.5_Lakh.pdf` → upload `JUDGE_DEMO2_Payment_Proof.pdf` → **Submit for review** | "A different bank's format, with two columns and different date styles, and OCR still reads it." |
| 2 Officer | Refresh the **Dashboard**. The new FDR is at the top of **Latest submissions**. Open it → **OCR review** | "The officer sees it instantly: the document, OCR values, confidence and submitted data side by side." |
| 2 Officer | **Mark documents checked** → remark → **Confirm** | Document status → *Document checked* |
| 2 Officer | **Bank verification** tab → **Bank confirmation received** → remark → **Record simulated outcome** | "Clearly labelled **SIMULATED**. Real confirmation must come from the issuing bank; a real bank API plugs into the same adapter later." |
| 1 Institution | Refresh the FDR → **Clearance** tab. All prerequisites are ticked → reason → **Submit clearance request** | "The server checks eligibility first: documents checked, bank confirmed, no open request." |
| 2 Officer | **Clearance Review** → **Review** → **Recommend approval** → remark → **Submit** | "The officer can only recommend." |
| 3 Senior | **Pending Approvals** → **Decide** → **Approve** → mandatory remark → **Record final decision** | "A **different** person decides. If the recommending officer tried, the server would return *403 Two-person rule*." |
| 3 Senior | **Open full case** → **Audit timeline** | "Every action, with user, role, timestamp and status before → after. The database rejects edits to this log." |

---

## If judges ask for technical proof

| Ask | Show |
|---|---|
| **"Is it really calling an API?"** | Click **Live Evidence** → **API calls**. Every request FastAPI received, newest first: method, path, status, time in ms and user. For example, `POST /api/fdrs/16/bank-verifications 201`. It refreshes every 2 s, so do an action and watch it appear. |
| **"Show me the server."** | The **backend window** (from `start.bat`) prints `API 201 POST /api/fdrs/16/bank-verifications 9.3 ms officer@demo… (officer)` for each request. The same lines are saved in `backend\data\logs\api.log`. |
| **"Is it really in a database?"** | **Live Evidence** → **Database**: the SQLite file path, its size and last-write time, live row counts per table (new rows flash green) and the latest `fdr_records` rows. In a terminal, double-click **`inspect-db.bat`** (`python -m app.cli inspect`). It reads the database file directly and prints the row counts, latest FDRs and latest audit entries. |
| **"Can I see the raw requests?"** | Press **F12** → **Network** tab → filter `api`. Click any request to see its JSON payload and response. |
| **"Can I call the API myself?"** | http://localhost:8000/docs (Swagger). Click **Authorize**, paste a token from `POST /api/auth/login`, and try endpoints live. |
| **"Is OCR real?"** | Upload the **phone photo**, or open **OCR review** → **Raw OCR text**. Or run `python -m app.cli check-ocr` in `backend`. |
| **"Can the audit log be edited?"** | `python -m pytest -k append_only` in `backend` runs the test showing that UPDATE and DELETE are rejected by both the code and database triggers. |
| **"Two-person rule?"** | `python -m pytest -k two_person` |

The evidence panel follows the same data-isolation rule as the app: an institution sees only its own requests
and records, while officers, seniors and admins see everything.

---

## Fallbacks during the live demo

| Problem | Do this |
|---|---|
| A sign-in page appears in a tab | Normal: each tab signs in separately. Click the role again. |
| Anything looks wrong mid-demo | Admin tab → **Live Evidence** → **Reset demo data** → type `RESET` (a backup is saved first). Or run `reset-demo.bat`. |
| "Cannot reach the SurakshaFD server" | The backend window was closed. Run `start.bat` again. |
| OCR shows "unavailable" | Tesseract isn't installed on this PC: `winget install UB-Mannheim.TesseractOCR`. The form can still be filled manually. |
| A field is marked *Needs review* | That's intended: low-confidence values are flagged, not guessed. Confirm it against the document. |

## Verified automatically
`e2e\run-judge-test.bat` runs **both demos end to end in Microsoft Edge**, with three tabs for three roles. Then it
**reads the SQLite file directly** to confirm every result was saved, and checks the API log. It takes about 1 minute,
and the 25 checks are listed in its output.
