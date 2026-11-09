"""Explainable forensic indicator (anomaly) detection.

These are *indicators*, not proof of fraud. Every finding stores an explicit
explanation, a detection method and traceable evidence rows so a reviewer can
see exactly why the indicator was raised.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from PIL import ExifTags, Image

from app.core.config import get_settings

SEVERITY_ORDER = ("info", "low", "medium", "high")

_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}
_EXIF_OFFSET_TAGS = {"ExifOffset", "GPSInfo"}

_IDENTIFIER_LABEL_RE = re.compile(
    r"\b(invoice|bill|receipt|po|purchase order|ref|reference|order|policy|account)"
    r"\s*(?:no\.?|number|#|id)?\s*[:\-]\s*([A-Z0-9][A-Z0-9\-/]{3,24})\b",
    re.IGNORECASE,
)

_FUTURE_YEARS_AHEAD = 1


def _parse_pdf_date(raw: str | None) -> datetime | None:
    """Parse PDF date strings such as ``D:20240101120000+05'30'``."""
    if not raw:
        return None
    match = re.search(r"(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?", raw)
    if not match:
        return None
    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    hour = int(match.group(4) or 0)
    minute = int(match.group(5) or 0)
    second = int(match.group(6) or 0)
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_exif_date(raw: str | None) -> datetime | None:
    """Parse EXIF timestamps such as ``2024:01:01 12:00:00``."""
    if not raw:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _finding(
    category: str,
    severity: str,
    title: str,
    explanation: str,
    detection_method: str,
    confidence: float | None = None,
    page_number: int | None = None,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "category": category,
        "severity": severity,
        "confidence": confidence,
        "title": title,
        "explanation": explanation,
        "detection_method": detection_method,
        "page_number": page_number,
        "evidence": evidence or [],
    }


def _metadata(document: Any) -> dict[str, Any]:
    payload = document.pdf_metadata or {}
    if isinstance(payload, dict):
        inner = payload.get("metadata")
        if isinstance(inner, dict):
            return inner
    return {}


def _image_exif(document: Any) -> dict[str, str]:
    """Read scalar EXIF tags from a stored image; {} when absent/unreadable."""
    if document.file_extension.lower() not in _IMAGE_EXTENSIONS:
        return {}
    try:
        path = get_settings().upload_dir / document.stored_filename
        if not path.exists():
            return {}
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return {}
            names = dict(ExifTags.TAGS)
            values: dict[str, str] = {}
            for tag_id, raw in exif.items():
                name = names.get(tag_id, str(tag_id))
                if name in _EXIF_OFFSET_TAGS:
                    continue
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", "ignore")
                if isinstance(raw, (dict, list, tuple)):
                    continue
                values[name] = str(raw)
            return values
    except Exception:
        return {}


def _image_findings(document: Any) -> list[dict[str, Any]]:
    if document.file_extension.lower() not in _IMAGE_EXTENSIONS:
        return []

    exif = _image_exif(document)
    if not exif:
        return [
            _finding(
                category="missing_metadata",
                severity="info",
                title="Image contains no EXIF metadata",
                explanation=(
                    "The image carries no EXIF metadata, so capture device, software "
                    "and timestamp provenance cannot be verified from the file itself. "
                    "Screenshots and re-encoded images commonly strip EXIF; this is a "
                    "completeness observation, not evidence of tampering."
                ),
                detection_method="image_exif_field_presence",
                confidence=1.0,
                evidence=[
                    {
                        "evidence_type": "metadata",
                        "source_ref": "image_exif",
                        "excerpt": "(empty)",
                        "explanation": "No EXIF tags were readable from the image.",
                        "page_number": None,
                    }
                ],
            )
        ]

    preview = ", ".join(f"{name}={value}" for name, value in list(exif.items())[:5])
    findings = [
        _finding(
            category="exif_metadata_present",
            severity="info",
            title="Image contains EXIF metadata",
            explanation=(
                f"The image carries EXIF metadata that can be reviewed for provenance: "
                f"{preview}. These values are self-reported by the file and can be "
                "edited, so they are investigative leads, not proof."
            ),
            detection_method="image_exif_field_read",
            confidence=1.0,
            evidence=[
                {
                    "evidence_type": "metadata",
                    "source_ref": f"image_exif.{name}",
                    "excerpt": value,
                    "explanation": f"EXIF tag '{name}'.",
                    "page_number": None,
                }
                for name, value in list(exif.items())[:12]
            ],
        )
    ]

    date_key = next(
        (
            key
            for key in ("DateTime", "DateTimeOriginal", "DateTimeDigitized")
            if exif.get(key)
        ),
        None,
    )
    moment = _parse_exif_date(exif.get(date_key) if date_key else None)
    now = datetime.now(timezone.utc)
    if moment and moment > now.replace(year=now.year + _FUTURE_YEARS_AHEAD):
        findings.append(
            _finding(
                category="timestamp_anomaly",
                severity="low",
                title="EXIF timestamp is in the future",
                explanation=(
                    f"The image reports an EXIF timestamp of {moment.isoformat()}, "
                    "which is later than the current date. This is unusual for a "
                    "capture made in the past and should be reviewed in context."
                ),
                detection_method="image_exif_future_date_check",
                confidence=0.9,
                evidence=[
                    {
                        "evidence_type": "metadata",
                        "source_ref": f"image_exif.{date_key}",
                        "excerpt": exif.get(date_key),
                        "explanation": "EXIF timestamp later than the current date.",
                        "page_number": None,
                    }
                ],
            )
        )

    return findings


def analyze_document(
    document: Any,
    extraction: Any | None,
    duplicate_of: Any | None = None,
) -> list[dict[str, Any]]:
    """Return explainable findings for a single document."""
    findings: list[dict[str, Any]] = []
    meta = _metadata(document) if document.file_extension == "pdf" else {}

    findings.extend(_metadata_findings(document, meta))
    findings.extend(_image_findings(document))
    findings.extend(_content_findings(document, extraction, meta))
    findings.extend(_identifier_findings(extraction))
    if duplicate_of is not None:
        findings.append(
            _finding(
                category="duplicate_file",
                severity="medium",
                title="Byte-identical copy of another document",
                explanation=(
                    "This file has the same SHA-256 hash as document "
                    f"'{duplicate_of.original_filename}' (id {duplicate_of.id}), meaning the "
                    "two uploads are byte-for-byte identical. This is an observation about "
                    "file duplication only and is not evidence of tampering."
                ),
                detection_method="sha256_hash_comparison",
                confidence=1.0,
                evidence=[
                    {
                        "evidence_type": "metadata",
                        "source_ref": "sha256_hash",
                        "excerpt": document.sha256_hash,
                        "explanation": "Matching SHA-256 hash across two document records.",
                        "page_number": None,
                    }
                ],
            )
        )

    findings.sort(key=lambda item: (-SEVERITY_ORDER.index(item["severity"]), item["category"]))
    return findings


def _metadata_findings(document: Any, meta: dict[str, Any]) -> list[dict[str, Any]]:
    if document.file_extension != "pdf":
        return []

    findings: list[dict[str, Any]] = []

    missing = [key for key in ("title", "author", "creator", "producer") if not meta.get(key)]
    if missing:
        findings.append(
            _finding(
                category="missing_metadata",
                severity="info",
                title=f"PDF is missing expected metadata: {', '.join(missing)}",
                explanation=(
                    "The PDF does not populate the following standard metadata fields: "
                    f"{', '.join(missing)}. Many legitimate tools leave these blank, so this "
                    "is a completeness observation, not evidence of modification."
                ),
                detection_method="pdf_metadata_field_presence",
                confidence=1.0,
                evidence=[
                    {
                        "evidence_type": "metadata",
                        "source_ref": f"pdf_metadata.{key}",
                        "excerpt": "(empty)",
                        "explanation": f"Metadata field '{key}' is absent or empty.",
                        "page_number": None,
                    }
                    for key in missing
                ],
            )
        )

    created = _parse_pdf_date(meta.get("creationDate"))
    modified = _parse_pdf_date(meta.get("modDate"))

    if created and modified and modified < created:
        findings.append(
            _finding(
                category="timestamp_anomaly",
                severity="medium",
                title="Modification date precedes creation date",
                explanation=(
                    f"The PDF reports a creation date of {created.isoformat()} but a "
                    f"modification date of {modified.isoformat()}, which is earlier. This "
                    "timestamp relationship is inconsistent and worth reviewing. It does "
                    "not by itself prove the file was altered."
                ),
                detection_method="pdf_date_relationship_check",
                confidence=0.9,
                evidence=[
                    {
                        "evidence_type": "metadata",
                        "source_ref": "pdf_metadata.creationDate",
                        "excerpt": meta.get("creationDate"),
                        "explanation": "Parsed creation timestamp.",
                        "page_number": None,
                    },
                    {
                        "evidence_type": "metadata",
                        "source_ref": "pdf_metadata.modDate",
                        "excerpt": meta.get("modDate"),
                        "explanation": "Parsed modification timestamp.",
                        "page_number": None,
                    },
                ],
            )
        )

    now = datetime.now(timezone.utc)
    for label, moment in (("creationDate", created), ("modDate", modified)):
        if moment and moment > now.replace(year=now.year + _FUTURE_YEARS_AHEAD):
            findings.append(
                _finding(
                    category="timestamp_anomaly",
                    severity="low",
                    title=f"PDF {label} is in the future",
                    explanation=(
                        f"The reported {label} ({moment.isoformat()}) is later than the "
                        "current date, which is unusual for a document produced in the past."
                    ),
                    detection_method="pdf_future_date_check",
                    confidence=0.95,
                    evidence=[
                        {
                            "evidence_type": "metadata",
                            "source_ref": f"pdf_metadata.{label}",
                            "excerpt": meta.get(label),
                            "explanation": "Timestamp later than the current date.",
                            "page_number": None,
                        }
                    ],
                )
            )

    if not meta.get("producer") and meta.get("creator"):
        findings.append(
            _finding(
                category="producer_anomaly",
                severity="low",
                title="Producer field empty while creator is present",
                explanation=(
                    f"The PDF identifies its creator as '{meta.get('creator')}' but leaves the "
                    "producer field empty. Some export/clean-up toolchains behave this way; it "
                    "is an observation about tooling, not a tamper signal on its own."
                ),
                detection_method="pdf_producer_creator_consistency",
                confidence=0.6,
                evidence=[
                    {
                        "evidence_type": "metadata",
                        "source_ref": "pdf_metadata.producer",
                        "excerpt": "(empty)",
                        "explanation": "Producer field is empty.",
                        "page_number": None,
                    },
                    {
                        "evidence_type": "metadata",
                        "source_ref": "pdf_metadata.creator",
                        "excerpt": str(meta.get("creator")),
                        "explanation": "Creator field is populated.",
                        "page_number": None,
                    },
                ],
            )
        )

    return findings


def _content_findings(document: Any, extraction: Any | None, meta: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    if extraction is None:
        return findings

    status = extraction.status
    method = extraction.method

    if status == "no_text":
        findings.append(
            _finding(
                category="empty_or_sparse_text",
                severity="low",
                title="No usable text layer found",
                explanation=(
                    "Native extraction found no meaningful text. For a PDF this usually "
                    "means the document is scanned or image-only; for an image it means no "
                    "OCR engine is available or OCR recognised nothing. This describes "
                    "extractability only - it says nothing about authenticity."
                ),
                detection_method="text_layer_density_check",
                confidence=1.0,
                evidence=[
                    {
                        "evidence_type": "extraction_status",
                        "source_ref": "text_extraction.status",
                        "excerpt": status,
                        "explanation": f"Extraction method used: {method}.",
                        "page_number": None,
                    }
                ],
            )
        )
    elif status == "completed" and extraction.word_count < 15:
        findings.append(
            _finding(
                category="empty_or_sparse_text",
                severity="info",
                title="Extracted text is unusually sparse",
                explanation=(
                    f"Only {extraction.word_count} word(s) were extracted across "
                    f"{extraction.page_count or 0} page(s). Sparse content limits how much "
                    "downstream analysis can conclude."
                ),
                detection_method="text_word_count_threshold",
                confidence=0.8,
                evidence=[
                    {
                        "evidence_type": "extraction_stats",
                        "source_ref": "text_extraction.word_count",
                        "excerpt": str(extraction.word_count),
                        "explanation": "Word count below the 15-word review threshold.",
                        "page_number": None,
                    }
                ],
            )
        )

    # Content dates that conflict with the PDF's own modification date.
    mod_date = _parse_pdf_date(meta.get("modDate")) or _parse_pdf_date(meta.get("creationDate"))
    if mod_date is not None and extraction.pages:
        future_hits: list[tuple[int, str]] = []
        for page in extraction.pages:
            text = page.get("text") or ""
            for match in re.finditer(r"\b(\d{4}-\d{2}-\d{2})\b", text):
                try:
                    value = datetime.fromisoformat(match.group(1))
                except ValueError:
                    continue
                if value.replace(tzinfo=timezone.utc) > mod_date:
                    future_hits.append((int(page.get("page_number") or 0), match.group(1)))
        if future_hits:
            page_number, raw = future_hits[0]
            findings.append(
                _finding(
                    category="inconsistent_dates",
                    severity="low",
                    title="Content date later than the PDF modification date",
                    explanation=(
                        f"The text contains the date {raw} on page {page_number}, which is "
                        f"later than the document's reported modification date "
                        f"({mod_date.date().isoformat()}). This can happen with templates, "
                        "planned dates or clock differences and should be reviewed in "
                        "context rather than treated as proof of alteration."
                    ),
                    detection_method="content_vs_metadata_date_comparison",
                    confidence=0.7,
                    page_number=page_number,
                    evidence=[
                        {
                            "evidence_type": "text",
                            "source_ref": f"page:{page_number}",
                            "excerpt": raw,
                            "explanation": "Date found in extracted page text.",
                            "page_number": page_number,
                        },
                        {
                            "evidence_type": "metadata",
                            "source_ref": "pdf_metadata.modDate",
                            "excerpt": meta.get("modDate"),
                            "explanation": "Document modification timestamp.",
                            "page_number": None,
                        },
                    ],
                )
            )

    return findings


def _identifier_findings(extraction: Any | None) -> list[dict[str, Any]]:
    """Detect the same identifier label carrying different values in one document."""
    if extraction is None or not extraction.pages:
        return []

    values_by_label: dict[str, dict[str, int]] = {}
    for page in extraction.pages:
        page_number = int(page.get("page_number") or 0)
        for match in _IDENTIFIER_LABEL_RE.finditer(page.get("text") or ""):
            label = match.group(1).lower()
            value = match.group(2).upper()
            values_by_label.setdefault(label, {}).setdefault(value, page_number)

    findings: list[dict[str, Any]] = []
    for label, mapping in values_by_label.items():
        if len(mapping) < 2:
            continue
        rendered = ", ".join(
            f"'{value}' (page {page})" for value, page in list(mapping.items())[:5]
        )
        findings.append(
            _finding(
                category="conflicting_identifiers",
                severity="medium",
                title=f"Conflicting '{label}' values in one document",
                explanation=(
                    f"The document contains more than one value for the '{label}' label: "
                    f"{rendered}. This may be legitimate (multiple orders on one invoice) or "
                    "may indicate copied content; it requires human review."
                ),
                detection_method="identifier_label_value_consistency",
                confidence=0.75,
                page_number=next(iter(mapping.values())),
                evidence=[
                    {
                        "evidence_type": "text",
                        "source_ref": f"label:{label}",
                        "excerpt": f"{label}: {value}",
                        "explanation": f"Conflicting value observed on page {page}.",
                        "page_number": page,
                    }
                    for value, page in mapping.items()
                ],
            )
        )

    return findings


def build_evidence_rows(
    document_id: str,
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Flatten findings into evidence rows keyed by their finding index."""
    rows: list[dict[str, Any]] = []
    for index, finding in enumerate(findings):
        for item in finding["evidence"]:
            rows.append(
                {
                    "finding_index": index,
                    "document_id": document_id,
                    "page_number": item.get("page_number"),
                    "evidence_type": item["evidence_type"],
                    "source_ref": item["source_ref"],
                    "excerpt": item.get("excerpt"),
                    "explanation": item["explanation"],
                }
            )
    return rows
