# VERITAS AI

**AI-Powered Document Forensics and Contextual Intelligence System**

VERITAS AI is a document investigation platform: upload PDFs and images, extract their text and
metadata, classify them, pull out entities, raise *explainable* forensic indicators with
traceable evidence, and compare multiple documents for shared and conflicting information.

> **Important principle:** every indicator produced by VERITAS AI is an *observation with an
> explanation*, never a verdict. The system does not declare documents fraudulent.

---

## Implemented features

| Area | Status |
|---|---|
| Secure document upload (PDF/PNG/JPG/JPEG, 20 MB limit, magic-byte validation, UUID storage, SHA-256) | ✅ verified |
| Document listing with pagination, filename search, sorting | ✅ verified |
| Document detail + deletion (DB rows, intelligence rows and stored file removed together) | ✅ verified |
| PDF metadata extraction (page count, title, author, creator, producer, dates) with PyMuPDF | ✅ verified |
| Native PDF text extraction, page-wise, with word/char statistics | ✅ verified |
| OCR for scanned PDFs and images (rapidocr-onnxruntime, confidence values per page) | ✅ verified |
| Rule-based document classification with fired-rule rationale | ✅ verified |
| Entity extraction (people, orgs, dates, money, email, phone, identifiers, URLs) with source text | ✅ verified |
| Deterministic factual document summary | ✅ verified |
| Explainable forensic indicators (metadata gaps, timestamp anomalies, sparse text, conflicting identifiers, duplicates…) | ✅ verified |
| Evidence traceability (each finding → source metadata field / page text) | ✅ verified |
| Cross-document comparison (shared entities, related records, conflicts) | ✅ verified |
| Dashboard statistics from real DB rows | ✅ verified |
| React frontend: dashboard, upload (drag & drop), library, detail investigation view, compare | ✅ verified |
| Backend test suite (pytest) | ✅ **52 passed** |
| Frontend type-check + production build | ✅ **passed** |

Not yet implemented: asynchronous/queued processing, LLM-based reasoning, pixel-level image
tamper detection, authentication, production-grade reporting exports. See
[Known limitations](#known-limitations).

---

## Repository layout

```
VERITAS-AI/
├── backend/                 Python 3.11 · FastAPI · SQLAlchemy 2 · SQLite · PyMuPDF · rapidocr
│   ├── app/
│   │   ├── api/routes/      health, documents, extraction, analysis, compare
│   │   ├── core/            config, database, errors
│   │   ├── models/          documents + intelligence tables
│   │   ├── schemas/         Pydantic request/response models
│   │   └── services/        validation, extraction, OCR, classification, entities,
│   │                        forensics, cross-document, analysis orchestration
│   ├── tests/               pytest suite (isolated temp DB + upload dir)
│   ├── uploads/             stored files (git-ignored)
│   └── veritas.db           SQLite database (git-ignored)
├── frontend/                React 19 · TypeScript · Vite · Axios · React Router · Lucide
│   └── src/
│       ├── components/      shared UI primitives, dropzone, table, dialog
│       ├── layouts/         application shell (sidebar + topbar)
│       ├── pages/           dashboard, upload, library, document detail, compare, 404
│       ├── services/        typed axios API client
│       ├── styles/          design system CSS
│       ├── types/           backend response types
│       └── utils/           formatting helpers
├── docs/                    architecture + API documentation
└── README.md
```

---

## Prerequisites

- **Python 3.11.9** (backend virtual environment already exists at `backend/.venv/`)
- **Node.js 22+** and npm (frontend)
- Windows 11 / PowerShell (commands below), macOS and Linux also work

---

## Run the backend

```powershell
cd C:\path\to\VERITAS-AI\backend
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

API docs: <http://127.0.0.1:8000/docs> · ReDoc: <http://127.0.0.1:8000/redoc>

## Run the frontend

```powershell
cd C:\path\to\VERITAS-AI\frontend
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api` to `http://localhost:8000`.

---

## Tests

```powershell
# Backend (52 tests, isolated temp DB and upload directory)
cd backend
.\.venv\Scripts\python.exe -m pytest

# Frontend type-check + production build
cd frontend
npm run build
```

---

## Configuration

Copy `backend/.env.example` to `backend/.env` and adjust if needed:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./veritas.db` | SQLite location (relative paths resolve against `backend/`) |
| `UPLOAD_DIR` | `./uploads` | Where validated files are stored |
| `MAX_UPLOAD_SIZE_MB` | `20` | Upload size cap |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | CORS allow-list (never `*` in production) |

Frontend: set `VITE_API_BASE` only if you want to bypass the Vite proxy and call the backend
directly (then add that origin to `ALLOWED_ORIGINS`).

---

## How analysis works

1. **Upload** → extension + magic-byte validation, SHA-256, UUID filename, PDF metadata.
2. **Extract** → PyMuPDF native text; scanned/image content falls back to OCR
   (`rapidocr-onnxruntime`) with per-page confidence; `no_text` is reported honestly.
3. **Analyze** → rule-based classification (with rationale), regex/heuristic entity extraction,
   deterministic summary, forensic indicators, evidence rows.
4. **Compare** → exact normalised matching across 2+ documents → shared values, related pairs,
   labelled conflicts.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/API.md](docs/API.md).

---

## Known limitations

- **Rule-based, not learned models.** Classification and indicators are transparent
  keyword/pattern rules. No deep-learning classifier is claimed.
- **OCR quality** depends on image resolution and the bundled rapidocr models; confidence is
  reported when provided, never fabricated.
- **Synchronous processing.** Extraction and analysis run inside the request (fine for the
  current ≤20 MB files; a job queue is the next step for large batches).
- **No authentication.** The app is intended for trusted local/single-user use for now.
- **Metadata anomalies are not tamper proof.** Timestamp or producer observations only prompt
  review.
- **No pixel-level image forensics** is performed or claimed.
- Entity extraction is regex/heuristic: high precision on common patterns, limited recall on
  unusual layouts, and it never invents missing values.

---

## Security notes

- Client-provided MIME types are ignored; content signatures (`%PDF-`, PNG, JPEG magic bytes)
  are checked server-side.
- Original filenames are never used as filesystem paths (server-generated UUID names).
- Uploads are streamed with a hard size limit; partial files are deleted on any failure.
- Upload directory is outside the web root and never exposed via the API.
- CORS is restricted to explicitly configured origins.
- Tests run against a temporary database and upload directory — they never touch real data.
