# SurakshaFD: Five-Minute SIH Judge Demo

**Before judges arrive (2 min):**
1. Double-click `reset-demo.bat` (fresh fictional data).
2. Double-click `start.bat` and wait for the login page at http://localhost:5173.
3. Keep `sample_documents\SAMPLE_FDR_Aravalli_10_Lakh.pdf` and `SAMPLE_Payment_Proof_Aravalli.pdf` handy (they're also downloadable on the Upload page).
4. Optional: open a second browser profile or private window for the officer, so you don't need to log out.

Password for every account: `Demo@123` (development only). The login page has one-click buttons.

---

### 0:00 · Opening (20 s)
> "AICTE receives security deposits as FDRs from thousands of institutions. Today they live in scattered files and inboxes, verification is manual, and maturity dates get missed. **SurakshaFD** turns every deposit into one auditable case file. Automation assists the scrutiny; authorised officials make every financial decision."

Point at the yellow banner: *demonstration prototype · fictional data · simulated bank verification*.

### 0:20 · Step 1: Institution logs in (20 s)
Click **Institution** on the login page.
> "Aravalli Institute sees its deposits, the amount on record, pending verification, discrepancies, and a 25-day maturity reminder that the system raised automatically."

### 0:40 · Steps 2–3: Upload and real OCR (50 s)
**Upload FDR** → drop `SAMPLE_FDR_Aravalli_10_Lakh.pdf`.
> "Tesseract OCR is running on our server right now. Nothing here is hard-coded."

When the form appears:
> "It read the bank name, FDR number, ₹10,00,000, issue and maturity dates, each with its own confidence score. The FDR number scored lower, so it's marked **Needs review** instead of being trusted blindly. The original document sits on the left for comparison."

### 1:30 · Step 4: Deliberate discrepancy (30 s)
Change **Principal amount** to `500000`.
> "Say a clerk types ₹5 lakh by mistake…"

The field turns red, and an **Amount mismatch detected** banner appears. Upload the payment proof (Step 3 card), then click **Run checks**.
> "Backend validation also flags it, along with duplicates, invalid dates and missing documents. It's a **warning, not an automatic rejection**: OCR can be wrong, so a human decides."

### 2:00 · Step 5: Correct and submit (15 s)
Click **Use document value**, then **Submit for review**.
> "The raw OCR reading and the confirmed values are both stored. The correction itself goes into the audit trail."

### 2:15 · Step 6: Officer review (30 s)
Sign out, then click **AICTE Officer** (or use the second window). Open the new case → **OCR review**.
> "The officer sees the document, the OCR values with confidence, what the institution confirmed, and what was submitted, side by side. Differences are highlighted in red."

Click **Mark documents checked** and enter a remark.

### 2:45 · Step 7: Simulated bank verification (30 s)
Go to the **Bank verification** tab → **Bank confirmation received** → enter a remark → **Record simulated outcome**.
> "We're explicit here: OCR can't prove an FDR is genuine. Only the issuing bank can. In this prototype the bank step is **simulated and labelled that way everywhere**. It sits behind an adapter interface, so a real bank or NeSL e-BG API can plug in without changing the workflow. Document status and bank status are tracked separately."

### 3:15 · Step 8: Dashboards and alerts (15 s)
Open **Dashboard**, then **Notifications**.
> "Officers see review queues, discrepancies, and 60/30/7-day maturity alerts. These come from a background job, which you can also trigger on demand."

### 3:30 · Step 9: Clearance request (30 s)
As the institution, open the FDR → **Clearance** tab. All prerequisites are ticked. Enter a reason → **Submit clearance request**.
As the officer, open **Clearance Review** → open the request → **Recommend approval** → enter remarks → submit.

### 4:00 · Step 10: Two-person approval (30 s)
Sign in as **Senior Approver** → **Pending Approvals** → **Decide** → **Approve** → enter mandatory remarks → **Record final decision**.
> "The officer who recommended can never give the final approval; the server enforces the two-person rule. And notice the last step on the tracker: **actual fund release happens outside this system**. We record the decision; we never move money."

(Optional proof: in `backend`, run `python -m pytest -k two_person` to show the test that blocks self-approval.)

### 4:30 · Step 11: Audit timeline (20 s)
Open the case → **Audit timeline** tab.
> "Every action is here with user, role, time, and the before → after status: upload, OCR, correction, validation, submission, review, simulated bank check, request, recommendation, decision. The log is append-only, and the database itself rejects edits or deletes."

### 4:50 · Close (10 s)
> "SurakshaFD: centralised records, assisted scrutiny, fewer missed deadlines, and decisions that stay with officials. Thank you."

---

### If a judge asks…
- **"Is the OCR real?"** Upload `SAMPLE_FDR_Aravalli_10_Lakh_scan.png` (a rotated scan image), or show **Raw OCR text** on the OCR review page.
- **"What about duplicates?"** Upload `SAMPLE_FDR_Duplicate_Number.pdf` as an institution, or open SFD-…-0005.
- **"Can rules change without code?"** Log in as **Administrator** → **Policy Management** → **New version** (for example, alert days `[90, 30, 7]`). It is versioned, has an effective date, and is audited.
- **"Reports?"** Administrator → **Reports**: filters plus CSV export.
- **"Can one institution see another's data?"** No. The server returns 404, and an automated test covers it.
- **"Production path?"** PostgreSQL via `DATABASE_URL`, real bank/NeSL adapter, HTTPS, Alembic migrations, DPDP-compliant retention.
