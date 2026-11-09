# VERITAS AI — API Reference

Base URL (development): `http://localhost:8000` · Interactive docs: `/docs` · ReDoc: `/redoc` ·
Schema: `/openapi.json`

All payloads are JSON unless noted. Errors use `{"detail": "<message>"}` with the appropriate
status code (`400`, `404`, `413`, `415`, `422`, `500`).

> **Note (auth layer):** since v1.2.0 every endpoint below — except `GET /api/v1/health`,
> `POST /api/v1/auth/register` and `POST /api/v1/auth/login` — requires an
> `Authorization: Bearer <token>` header (`401` otherwise) and is scoped to the signed-in
> owner (`404` for foreign resources). Additional route groups:
>
> - **Auth:** `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`
> - **Investigations:** `GET|POST /api/v1/investigations`, `GET|PATCH|DELETE /api/v1/investigations/{id}`,
>   `GET /api/v1/investigations/{id}/report` (PDF download)
> - Upload accepts an optional `investigation_id` form field; document responses include
>   `investigation_id`.
>
> The live OpenAPI schema at `/openapi.json` is the authoritative reference.

---

## Health

### `GET /api/v1/health`

```json
{ "status": "ok" }
```

---

## Documents

### `POST /api/v1/documents/upload` · `201`

Multipart form field `file` — PDF, PNG, JPG or JPEG, ≤ 20 MB, non-empty, valid signature.

```json
{
  "id": "8f14e45f-...-uuid",
  "original_filename": "invoice.pdf",
  "file_extension": "pdf",
  "mime_type": "application/pdf",
  "file_size": 18432,
  "sha256_hash": "3a7bd3e2360a3d29eea436fcf7e44c00...",
  "upload_timestamp": "2026-11-09T10:20:30Z",
  "processing_status": "completed",
  "page_count": 2,
  "pdf_metadata": { "page_count": 2, "metadata": { "producer": "...", "title": "..." } }
}
```

| Status | Cause |
|---|---|
| 400 | Empty file, corrupt PDF, password-protected PDF, signature/extension mismatch |
| 413 | Exceeds `MAX_UPLOAD_SIZE_MB` |
| 415 | Unsupported extension |

### `GET /api/v1/documents` · `200`

Query: `page` (≥1, default 1), `page_size` (1–100, default 20), `search` (case-insensitive
filename substring).

```json
{ "items": [ { "...": "DocumentResponse" } ], "total": 12, "page": 1, "page_size": 20 }
```

### `GET /api/v1/documents/{id}` · `200 / 404`

Full `DocumentResponse` (never includes `stored_filename` or paths).

### `DELETE /api/v1/documents/{id}` · `200 / 404`

```json
{ "message": "Document deleted successfully." }
```

Removes the document row, all intelligence rows (extraction, analysis, entities, findings,
evidence) and the stored file.

---

## Text extraction

### `POST /api/v1/documents/{id}/extract` · `200 / 404 / 409`

Runs (or re-runs) extraction and persists the result.

```json
{
  "document_id": "…",
  "status": "completed",          // pending | completed | no_text | failed
  "method": "native",             // native | ocr | none
  "page_count": 2,
  "char_count": 1840,
  "word_count": 312,
  "ocr_available": true,
  "error": null,
  "pages": [
    { "page_number": 1, "text": "…", "char_count": 900, "word_count": 160,
      "method": "native", "confidence": null }
  ]
}
```

- Native PDF extraction via PyMuPDF; pages with a thin/no text layer fall back to OCR
  (200 DPI rasterisation + rapidocr), reported per page with engine confidence.
- Images have no native layer: OCR only; if no engine is installed the result is
  `no_text` with an explanatory `error` (never fabricated text).

### `GET /api/v1/documents/{id}/text` · `200 / 404`

Returns the stored extraction (404 when extraction has not run yet).

---

## Analysis & understanding

### `POST /api/v1/documents/{id}/analyze` · `200 / 404`

Runs the full pipeline (extract if needed → classify → entities → findings → summary) and
returns the bundle. Idempotent: re-running replaces previous rows.

### `GET /api/v1/documents/{id}/analysis` · `200 / 404`

Returns the bundle, running analysis on demand if it has not happened yet.

```json
{
  "document_id": "…",
  "extraction": { "…": "ExtractionResponse" },
  "classification": {
    "status": "completed",
    "category": "invoice",
    "category_label": "Invoice",
    "confidence": 0.71,
    "rationale": [ { "rule": "Contains the word 'invoice'", "category": "invoice",
                     "weight": 3.0, "matched": "INVOICE" } ],
    "method": "rule_based_baseline"
  },
  "summary": "'invoice.pdf' is classified as Invoice (rule-based baseline, confidence 71%)…",
  "entities": [
    { "id": "…", "entity_type": "email", "value": "a@b.com",
      "normalized_value": "a@b.com", "confidence": 0.98,
      "page_number": 1, "source_text": "Email: a@b.com" }
  ],
  "findings": [
    { "id": "…", "category": "timestamp_anomaly", "severity": "medium",
      "confidence": 0.9, "title": "Modification date precedes creation date",
      "explanation": "…", "detection_method": "pdf_date_relationship_check",
      "page_number": null, "created_at": "…",
      "evidence": [ { "id": "…", "page_number": null, "evidence_type": "metadata",
                      "source_ref": "pdf_metadata.creationDate",
                      "excerpt": "D:20240601000000Z", "explanation": "Parsed creation timestamp." } ] }
  ],
  "disclaimer": "Findings are explainable indicators … not a determination of fraud or tampering."
}
```

Entity types: `person_name`, `organization`, `date`, `money`, `email`, `phone`,
`document_identifier`, `url`.
Finding categories: `missing_metadata`, `timestamp_anomaly`, `producer_anomaly`,
`empty_or_sparse_text`, `inconsistent_dates`, `conflicting_identifiers`, `duplicate_file`.
Severities: `info` < `low` < `medium` < `high`.

### `GET /api/v1/documents/{id}/findings` · `200 / 404`

Array of findings, each with its `evidence[]`.

### `GET /api/v1/documents/{id}/entities` · `200 / 404`

Array of extracted entities.

### `GET /api/v1/documents/{id}/evidence` · `200 / 404`

All evidence rows for the document.

### `GET /api/v1/stats` · `200`

```json
{
  "total_documents": 3, "processed_documents": 3, "failed_documents": 0,
  "documents_with_text": 2, "total_findings": 5,
  "findings_by_severity": { "info": 2, "low": 2, "medium": 1 },
  "total_entities": 24,
  "recent_documents": [ { "id": "…", "original_filename": "…", "file_extension": "pdf",
                          "upload_timestamp": "…", "processing_status": "completed",
                          "file_size": 18432 } ]
}
```

---

## Cross-document comparison

### `POST /api/v1/compare` · `200 / 404 / 422`

```json
{ "document_ids": ["uuid-1", "uuid-2"] }
```

2–25 distinct ids; documents without prior analysis are analysed automatically.

```json
{
  "document_ids": ["…", "…"],
  "document_names": ["a.pdf", "b.pdf"],
  "shared_entities": [
    { "entity_type": "person_name", "value": "John Smith",
      "normalized_value": "john smith", "document_count": 2,
      "occurrences": [ { "document_id": "…", "document_name": "a.pdf",
                         "page_number": 1, "source_text": "Name: John Smith",
                         "confidence": 0.85 } ],
      "explanation": "The value 'John Smith' (person_name) appears in 2 documents." }
  ],
  "related_records": [
    { "document_ids": ["…", "…"], "document_names": ["a.pdf", "b.pdf"],
      "shared_values": [ { "entity_type": "organization", "value": "Acme Robotics Pvt Ltd" } ],
      "explanation": "'a.pdf' and 'b.pdf' share 2 distinct extracted values." }
  ],
  "conflicts": [
    { "conflict_type": "identifier_label_mismatch", "field": "invoice", "subject": null,
      "values": [ { "value": "INV-2024-0099", "documents": [ { "document_name": "a.pdf" } ] } ],
      "explanation": "The 'invoice' label carries different values … Review in context.",
      "severity": "medium" },
    { "conflict_type": "person_contact_mismatch", "field": "email", "subject": "john smith",
      "values": [ { "value": "billing@acme.com", "documents": [ … ] } ],
      "explanation": "Documents mentioning the same person contain different email values …",
      "severity": "low" }
  ],
  "summary": { "documents_compared": 2, "shared_entity_count": 2,
               "related_record_count": 1, "conflict_count": 2 },
  "method": "exact_normalized_matching",
  "disclaimer": "Matches and conflicts are explainable observations … not proof of fraud …"
}
```

Conflict types: `identifier_label_mismatch` (same label, different values, across documents
that also share a person/organization), `person_contact_mismatch` (same person, different
email/phone values).

---

## Status codes summary

| Code | Meaning |
|---|---|
| 200 | Success |
| 201 | Document created |
| 400 | Invalid file content / empty / corrupt / password-protected |
| 404 | Document or extraction not found |
| 409 | Operation not possible for this document state |
| 413 | File too large |
| 415 | Unsupported file type |
| 422 | Validation error (pagination bounds, compare payload) |
| 500 | Storage/database failure |
