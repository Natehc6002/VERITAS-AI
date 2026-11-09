# VERITAS AI — Backend

FastAPI service for secure document ingestion, extraction, understanding and forensic analysis.

- Python 3.11.9 · FastAPI · SQLAlchemy 2.x · SQLite · Pydantic 2 · PyMuPDF · rapidocr-onnxruntime

## Run

```powershell
cd backend
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

Interactive API docs: `http://127.0.0.1:8000/docs`

> The virtual environment `backend/.venv/` already exists — do not recreate it. Python 3.13 may
> exist on the machine; it is not used by this project.

## Configuration

Settings load from environment variables / `backend/.env` (see `.env.example`):

| Variable | Default |
|---|---|
| `APP_NAME` | `VERITAS AI` |
| `DEBUG` | `false` |
| `DATABASE_URL` | `sqlite:///./veritas.db` |
| `UPLOAD_DIR` | `./uploads` |
| `MAX_UPLOAD_SIZE_MB` | `20` |
| `ALLOWED_ORIGINS` | `http://localhost:5173` |

Relative SQLite/upload paths resolve against the `backend/` directory.

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

- **52 tests, all passing.**
- `tests/conftest.py` points `DATABASE_URL` and `UPLOAD_DIR` at a fresh temporary directory
  before the app is imported, so tests never touch real data.
- Coverage: health/OpenAPI/CORS, PDF + image upload, invalid/oversized/empty uploads, listing,
  pagination, search, detail, deletion, text extraction (native/scanned/image), OCR status,
  classification, entities, summary, timestamp-anomaly findings, evidence, statistics, cascade
  deletion, cross-document shared entities/related records/conflicts, compare validation.

## Package map

```
app/
├── main.py                 app factory, CORS, lifespan, error handlers
├── api/routes/
│   ├── health.py           GET  /api/v1/health
│   ├── documents.py        POST/GET/DELETE documents, pagination + search
│   ├── extraction.py       POST /documents/{id}/extract · GET /documents/{id}/text
│   ├── analysis.py         POST/GET analysis, findings, entities, evidence, GET /stats
│   └── compare.py          POST /compare
├── core/
│   ├── config.py           pydantic-settings
│   ├── database.py         engine, session, Base, init_db
│   └── errors.py           domain errors → HTTP status codes
├── models/
│   ├── document.py         Document ORM
│   └── intelligence.py     TextExtraction, DocumentAnalysis, Entity, Finding, Evidence
├── schemas/                response/request models
└── services/
    ├── file_validation.py  extension + magic-byte checks, streaming save, hashing
    ├── document_service.py upload/list/get/delete business logic
    ├── text_extraction.py  PyMuPDF native extraction, scanned detection, OCR fallback
    ├── ocr_service.py      lazy OCR backend discovery (rapidocr → pytesseract)
    ├── classification.py   explainable keyword/pattern baseline
    ├── entity_extraction.py regex/heuristic entities with source context
    ├── forensics.py        explainable indicators + evidence rows
    ├── cross_document.py   shared values, related records, conflicts
    └── analysis_service.py pipeline orchestration + dashboard stats
```

## OCR

`app/services/ocr_service.py` resolves exactly one backend at runtime:

1. `rapidocr-onnxruntime` (installed, self-contained CPU engine — default)
2. `pytesseract` (requires a system Tesseract binary)

If neither import succeeds, OCR-dependent operations degrade gracefully: extraction returns
`no_text` with an explicit message stating the missing dependency. Nothing is faked.

## Design rules

- Expected failures raise `VeritasError` subclasses and map to correct HTTP status codes.
- The API never exposes `stored_filename` or filesystem paths.
- Delete removes the document row, all intelligence rows (`TextExtraction`, `DocumentAnalysis`,
  `Entity`, `Finding`, `Evidence`) and the stored file, in that order, with rollback on DB error.
