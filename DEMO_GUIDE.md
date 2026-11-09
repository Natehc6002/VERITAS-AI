# VERITAS AI — Demo Guide (Hackathon)

Step-by-step guide to run and present VERITAS AI. All commands are **Windows PowerShell**.

---

## 1. Prerequisites

- Python 3.11 virtual environment at `backend\.venv\` (ships with the repo checkout)
- Node.js 22+ with npm
- Two terminals (PowerShell windows)

No API keys, no external services, no internet required after install.

---

## 2. Startup commands

### Terminal 1 — Backend (FastAPI, port 8000)

```powershell
cd C:\Users\DARSHAN I S\Desktop\VERITAS-AI\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Expected output: `Application startup complete.` and a warning that `AUTH_SECRET_KEY`
is not configured (harmless for a local demo — see Troubleshooting).

### Terminal 2 — Frontend (Vite, port 5173)

```powershell
cd C:\Users\DARSHAN I S\Desktop\VERITAS-AI\frontend
npm run dev
```

Expected output: `Local: http://localhost:5173/`.

### Verify both are up

```powershell
(Invoke-WebRequest -Uri http://127.0.0.1:8000/api/v1/health -UseBasicParsing).Content
(Invoke-WebRequest -Uri http://localhost:5173/api/v1/health -UseBasicParsing).Content
```

Both must return `{"status":"ok"}`.

---

## 3. Application URLs

| URL | Purpose |
|---|---|
| <http://localhost:5173> | **Demo app (open this in the browser)** |
| <http://127.0.0.1:8000/docs> | Interactive API docs (Swagger) |
| <http://127.0.0.1:8000/redoc> | API docs (ReDoc) |
| <http://localhost:5173/api/v1/health> | Health check through the dev proxy |

The frontend proxies `/api` to the backend automatically — the browser only ever talks to
port 5173.

---

## 4. Demo workflow (run in this order)

### Step 1 — Create an account (shows authentication)

Open <http://localhost:5173> → redirected to **Sign in** → click **Create one**.

- Register with any valid email and a password of **at least 8 characters**.
- You are signed in automatically and land on the dashboard.

**Show judges:** protected routes — the app cannot be used without an account; sessions
are HMAC-signed bearer tokens with an expiry.

**Expected output:** dashboard loads; the sidebar shows your email and a **Sign out** button.

> Do not rely on a pre-existing account: registering live takes 5 seconds and demonstrates
> the auth flow. Credentials are never stored in this repository.

### Step 2 — Upload documents (shows secure ingestion)

Open **Upload** in the sidebar. Drag and drop (or pick):

1. Any **PDF** (contract, invoice, letter…)
2. A **photo/screenshot containing text** (JPEG or PNG) — this exercises OCR
3. Optionally a second PDF for comparison later

**Show judges:** client MIME types are ignored server-side; magic bytes are validated;
files are stored under UUID names; SHA-256 is computed; 20 MB cap enforced.

**Expected output:** each file shows a progress state, then a green success row.
Unsupported files (e.g. `.exe`) are rejected with a clear error.

### Step 3 — Extract text / OCR

Open the image document in the library. Extraction runs automatically (or press
**Re-extract**).

**Show judges:** the extraction panel shows the method — `native` for text PDFs,
`ocr` (rapidocr, per-page confidence) for scans/images — and honest `no_text` status when
nothing is readable.

**Expected output:** word/char counts, page-wise text. OCR of a clear screenshot typically
recognises the visible text (amounts, invoice numbers…).

### Step 4 — Forensic analysis (classification, entities, findings)

Still on the document detail page, view **Classification**, **Entities** and
**Findings**.

**Show judges:**
- classification with the *fired rule* that produced it (explainable, not a black box)
- entities with the exact source text they came from
- forensic indicators — each with severity, explanation, detection method and evidence
  rows (e.g. *missing PDF metadata*, *sparse text*, *EXIF provenance* on images)
- the standing disclaimer: indicators are observations for human review, **never a verdict**

**Expected output:** for an image, an `Image contains EXIF metadata` finding with the
actual EXIF values as evidence (or an honest "no EXIF" observation).

### Step 5 — Compare documents

Open **Compare**, select **two or more documents**, run the comparison.

**Show judges:** shared entities (exact **and** fuzzy near-matches with a similarity
score, e.g. `Global Trade Holdings Ltd` ≈ `Global Trading Holdings Ltd`), related record
pairs, labelled conflicts, and the methodology string.

**Expected output:** a shared/conflict table; near-identical organisation names are
matched with `similarity ≥ 0.80` and flagged for **human review**.

### Step 6 — Investigations (case container)

Open **Investigations** → create a case (e.g. `Vendor dispute Q4`) → from **Upload**,
assign documents to it.

**Show judges:** documents are grouped per investigation; everything is owner-scoped.

**Expected output:** the investigation row shows document counts.

### Step 7 — Download the forensic PDF report (headline feature)

On the investigation row, click **Report PDF**.

**Show judges:** the generated report — cover, document info with **SHA-256 hashes**,
entities, every finding with its evidence and source references, the cross-document
comparison section, methodology and disclaimer.

**Expected output:** a multi-page PDF downloads in the browser (`veritas-report-*.pdf`).

### Step 8 — Show that unauthorized access is rejected

Two quick proofs (30 seconds):

1. Open the browser dev tools → Network, **Sign out**, then try to open the library —
   the app redirects to Sign in; API calls return `401`.
2. Register a **second account** in a private window, then try to open/download the first
   account's document or report via its URL — the API returns `404` (no existence leak).

**Expected output:** `401` without a token, `404` for another user's resources.

---

## 5. What NOT to claim

See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md). In particular: processing is
synchronous, there is no background queue, classification is rule-based (no LLM), and
every forensic finding requires human verification.

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Browser shows proxy/network errors; `localhost:5173` loads but data fails | Backend not running | Start Terminal 1; re-check `/api/v1/health` |
| `Address already in use` on port 8000/5173 | A previous process still holds the port | Stop it (commands below) and restart |
| `401` on every request after a backend restart | Ephemeral signing key (no `AUTH_SECRET_KEY` set) invalidated old tokens | Sign in again (or set `AUTH_SECRET_KEY` in `backend\.env`) |
| Login fails after you restart the backend, but you did not change the password | Same as above — tokens are signed with a per-process key | Sign in again |
| OCR panel says no engine installed | `rapidocr_onnxruntime` missing from the venv | `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` |
| First OCR run is slow (several seconds) | ONNX model warm-up | Expected; subsequent pages are faster |
| `npm run dev` fails with missing modules | `node_modules` not installed | `cd frontend; npm install` |
| Windows Store opens instead of `python` | Using system `python` | Always use `.\.venv\Scripts\python.exe` |
| Demo feels stale after pulling new code | Old servers still running | Stop both servers, restart (below) |

---

## 7. How to stop both servers

- **Preferred:** click in each terminal and press `Ctrl+C`.
- If a terminal is lost, stop by port:

```powershell
# Backend (8000)
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# Frontend (5173)
Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

Verification: both health-check commands from Section 2 should now fail.

---

## 8. Reset the demo data (optional)

All data lives in two git-ignored local paths — deleting them gives a clean slate
(the next startup recreates both):

```powershell
cd C:\Users\DARSHAN I S\Desktop\VERITAS-AI\backend
Remove-Item .\veritas.db -ErrorAction SilentlyContinue
Remove-Item .\uploads\* -Recurse -ErrorAction SilentlyContinue
```

You will need to register a new account afterwards. **Never delete these files on a
machine whose data you have not backed up.**
