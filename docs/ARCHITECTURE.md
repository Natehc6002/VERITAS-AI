# VERITAS AI — Architecture

## Overview

```
┌─────────────────────────────┐        ┌──────────────────────────────────────────┐
│  React SPA (Vite, :5173)    │  HTTP  │  FastAPI (:8000)                        │
│  ─ AppShell (sidebar/topbar)│ ─────▶ │  ─ routes: health/documents/extraction/ │
│  ─ pages: dashboard, upload,│ proxy  │    analysis/compare                     │
│    library, detail, compare │        │  ─ services (business logic)            │
│  ─ typed axios client       │        │  ─ domain errors → HTTP status codes    │
└─────────────────────────────┘        └───────┬──────────────────┬───────────────┘
                                               │                  │
                                       ┌───────▼──────┐   ┌───────▼────────────┐
                                       │ SQLite       │   │ File store         │
                                       │ veritas.db   │   │ uploads/<uuid>.ext │
                                       │ SQLAlchemy 2 │   │ (never web-exposed)│
                                       └──────────────┘   └────────────────────┘
```

The frontend talks to the backend through relative `/api/v1/*` URLs. In development Vite
proxies them to `localhost:8000`; CORS on the backend additionally allows
`http://localhost:5173` for direct calls.

## Backend layers

| Layer | Responsibility | Rule |
|---|---|---|
| `api/routes/*` | HTTP contracts: status codes, query/body validation, response models | No business logic |
| `services/*` | All orchestration and domain logic | No FastAPI request objects (except `UploadFile`) |
| `models/*` | SQLAlchemy 2.0 typed ORM mappings | No HTTP concerns |
| `schemas/*` | Pydantic request/response shapes | Never expose `stored_filename` or paths |
| `core/*` | Settings, engine/session, error hierarchy | Imported everywhere |

### Data model

- **`documents`** — id (UUID), original/stored filename, extension, mime, size, sha256,
  upload timestamp, processing status, page count, `pdf_metadata` JSON.
- **`text_extractions`** (1:1) — status (`pending/completed/no_text/failed`), method
  (`native/ocr/none`), full text, per-page JSON (`text`, counts, method, confidence), OCR
  availability, error.
- **`document_analyses`** (1:1) — status, category + confidence + fired-rule rationale,
  deterministic summary.
- **`entities`** — type, value, normalised value, confidence, page, source text.
- **`findings`** — category, severity, confidence, title, explanation, detection method, page.
- **`evidence`** — links a finding (or document) to a source: type, `source_ref`
  (e.g. `pdf_metadata.modDate`, `page:3`), excerpt, explanation, page number.

All intelligence tables use `ON DELETE CASCADE` foreign keys to `documents`, **and**
`analysis_service.delete_analysis_rows()` explicitly removes them during deletion so the app
behaves correctly even with SQLite FK enforcement disabled (SQLAlchemy default).

## Processing pipeline

```
upload ──▶ validate (extension → magic bytes → size → empty) ──▶ stream to <uuid>.ext
        ──▶ SHA-256 while streaming ──▶ PyMuPDF metadata (PDFs) ──▶ DB row
        (any failure ⇒ partial file deleted, no DB row)

extract ──▶ PyMuPDF page text
        ──▶ total chars < 40 ⇒ "scanned?" ──▶ OCR (rapidocr) per page at 200 DPI
        ──▶ persist status/method/pages/stats  (images: OCR only)

analyze ──▶ extract (if missing) ──▶ classification (rules + rationale)
        ──▶ entity extraction (regex/heuristic, page-aware)
        ──▶ forensics (metadata/content/identifier checks → findings + evidence)
        ──▶ deterministic summary ──▶ persist everything

compare ─▶ ensure each document analysed ─▶ normalise entities ─▶ exact-value index
        ─▶ shared (≥2 docs) · related pairs (≥2 shared values) · conflicts
```

### Explainability guarantees

- Classification returns **which rules fired** with the matched text and weight.
- Findings store `detection_method`, a human explanation and ≥1 evidence row referencing an
  exact metadata field or page text.
- Cross-document results name every source document and page for each occurrence.
- Nothing is inferred beyond patterns: no fabricated text, confidence or authenticity claims.

## Frontend

- **AppShell** — sticky sidebar (nav + backend health dot), topbar with route-aware title.
- **Pages** are self-contained: fetch on mount, render loading/empty/error states, expose
  retry where meaningful.
- **API client** (`services/api.ts`) is the only place that touches axios; `errorMessage()`
  normalises FastAPI `detail` payloads (string or validation array), timeouts and offline
  cases.
- **Types** in `types/api.ts` mirror backend Pydantic schemas; a schema change breaks the
  `tsc` build rather than silently corrupting the UI.

## Security posture

| Threat | Mitigation |
|---|---|
| Malicious file content | Magic-byte signature check server-side; client MIME ignored |
| Path traversal via filename | Original name never joins a path; UUID storage names |
| Oversized uploads | Streaming cap at `MAX_UPLOAD_SIZE_MB`, partial file removed |
| Empty / corrupt uploads | Rejected with 400; corrupt PDFs caught by PyMuPDF before the DB row |
| Path disclosure | `stored_filename` and absolute paths excluded from all responses |
| CORS abuse | Explicit origin allow-list (no wildcards) |
| DB/file inconsistency | Single transactional delete order with rollback, then file removal |

## Current constraints (by design, for this milestone)

- Extraction/analysis run synchronously in the request thread (files ≤ 20 MB).
- SQLite with `check_same_thread=False` and short-lived sessions per request.
- Authentication and owner-scoped multi-user isolation are implemented (register/login,
  bearer tokens, every data endpoint owner-checked with 404 on foreign access); there are
  no sharing/roles and no organisation layer.
- No queue, no external model APIs.
