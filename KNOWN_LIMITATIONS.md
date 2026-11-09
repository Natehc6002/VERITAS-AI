# VERITAS AI — Known Limitations

Honest inventory of what this project does **not** do. Nothing in the README, demo
script or UI should be read as claiming these capabilities.

---

## Explicitly required disclosures

### 1. Asynchronous / background processing is NOT implemented
Uploads, text extraction (including OCR), classification, entity extraction and
forensic analysis all run **synchronously inside the HTTP request**. There is no job
queue, no worker pool and no progress polling — the browser waits for the response.
This is acceptable for the demo's ≤20 MB files on a local machine, but it will not
scale to large batches or slow OCR-heavy workloads. A queue/worker design is the
documented next step, not a shipped feature.

### 2. No automated browser UI-click testing is available
The frontend is verified by:
- TypeScript type-checking + production build (`npm run build`), and
- API-level end-to-end tests that exercise exactly the endpoints the UI calls
  (through the same Vite proxy the browser uses).

There is **no** Selenium/Playwright/CTest-driven click-through of the React UI in this
repository. UI behaviour (routing, buttons, download trigger) has been exercised
manually, not by an automated browser test. Do not claim full UI test coverage.

### 3. OCR and automated forensic findings require human verification
- **OCR** (rapidocr, bundled ONNX models) can misread low-resolution, skewed or
  stylised text. Confidence values are reported when the engine provides them — they
  are not a guarantee. Verify extracted values against the original document.
- **Forensic findings are indicators, not verdicts.** Classification, entities,
  timestamp/metadata anomalies, fuzzy matches and conflict labels are produced by
  deterministic rules and heuristics. Every one of them can produce false positives or
  miss real issues. The system never declares a document authentic or fraudulent;
  each finding carries an explanation and evidence precisely so a human can review it.

---

## Additional limitations

### Processing & intelligence
- **Rule-based, not learned models.** Classification and indicators are transparent
  keyword/pattern rules — no LLM, no deep-learning classifier, no model API calls.
- **No pixel-level image forensics.** Image handling covers text OCR and EXIF metadata
  observations only; no splicing detection, no error-level analysis, no noise analysis.
- **Entity extraction is regex/heuristic** — high precision on common patterns, limited
  recall on unusual layouts; it never invents missing values.
- **Fuzzy matching** compares normalised strings with `difflib` (threshold 0.80) for
  organisation/person/address values only. It can both miss variants and pair unrelated
  similar names; results are labelled for human review.

### Platform
- **SQLite** single-file database (`check_same_thread=False`, short-lived sessions) —
  demo scale only, no horizontal scaling.
- **Synchronous pipeline** (see disclosure #1).
- **Supported upload types: PDF, PNG, JPG, JPEG only** (20 MB cap). No Office formats,
  no email containers, no video/audio.
- **Single-tenant-by-ownership model**: documents belong to exactly one user and one
  investigation; there is no sharing/collaboration, no roles, no organisations.

### Authentication (demo-grade)
- **No password reset, no email verification, no MFA, no login rate limiting.**
- Tokens are stored in the browser's `localStorage` (XSS exposure) over plain HTTP on
  localhost.
- If `AUTH_SECRET_KEY` is not configured, an **ephemeral per-process key** signs tokens:
  **every backend restart invalidates all sessions** (users must sign in again). This is
  announced as a startup warning in the server log.
- See [SECURITY_NOTES.md](SECURITY_NOTES.md) for the full threat model and the
  pre-deployment checklist.

### Reporting
- The PDF report reflects data present at generation time; it is regenerated on demand,
  not versioned or signed.
- Reports contain whatever was extracted — including possible OCR errors — verbatim.

---

## Data & privacy (local demo)

- All data lives in git-ignored local files: `backend/veritas.db` (database) and
  `backend/uploads/` (stored files). Nothing is sent to external services; OCR and
  analysis run locally.
- No telemetry, no analytics, no third-party API calls at runtime.
