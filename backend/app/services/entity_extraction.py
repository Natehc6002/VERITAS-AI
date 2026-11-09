"""Explainable, regex/heuristic entity extraction.

Every extracted entity carries the source text it was found in, so results can
be traced back to the document. Nothing is invented: only pattern matches are
reported, and confidence reflects how specific the pattern is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

ENTITY_TYPES = (
    "person_name",
    "organization",
    "date",
    "money",
    "email",
    "phone",
    "document_identifier",
    "url",
)


@dataclass(frozen=True)
class EntityHit:
    entity_type: str
    value: str
    normalized_value: str | None
    confidence: float
    source_text: str
    span: tuple[int, int]


_DATE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"), "iso"),
    (re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-](?:\d{2}|\d{4}))\b"), "slash"),
    (
        re.compile(
            r"\b(\d{1,2}(?:st|nd|rd|th)?\s+"
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r",?\s+\d{4})\b",
            re.IGNORECASE,
        ),
        "long",
    ),
    (
        re.compile(
            r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})\b",
            re.IGNORECASE,
        ),
        "long",
    ),
]

_MONEY_RE = re.compile(
    r"(?:"
    r"(?:USD|EUR|GBP|INR|AUD|CAD|JPY|CNY)\s?[\d,]+(?:\.\d{1,2})?"
    r"|[\$€£¥₹]\s?[\d,]+(?:\.\d{1,2})?"
    r"|\b[\d,]+(?:\.\d{1,2})?\s?(?:USD|EUR|GBP|INR|AUD|CAD|JPY|CNY)\b"
    r")",
    re.IGNORECASE,
)

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)\d{3,4}[\s.-]?\d{3,4}(?!\w)"
)

_IDENTIFIER_RE = re.compile(
    r"\b(?:"
    r"(?:invoice|bill|receipt|purchase|order|po|ref(?:erence)?|quote|ticket|case|"
    r"passport|license|licence|national\s*id|aadhaar|pan|account|customer|member|"
    r"policy|claim|registration|serial|tracking|student|employee|tax|ssn|gstin)"
    r"\s*(?:no\.?|number|#|id|code)?\s*[:\-]?\s*"
    r")([A-Z0-9][A-Z0-9\-/]{3,24})",
    re.IGNORECASE,
)

_URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)

_PERSON_LABEL_RE = re.compile(
    r"\b(?:name|applicant|beneficiary|customer|employee|student|policyholder|"
    r"contact\s*person|issued\s*to|author(?:ized)?(?:ised)?\s*signatory)\s*[:\-]\s*"
    r"([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,4})",
    re.IGNORECASE,
)

_PERSON_TITLE_RE = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof|Sir|Madam)\.?\s+([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3})"
)

_ORG_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z0-9&.'-]+){0,6}\s+"
    r"(?:Inc\.?|Ltd\.?|LLC|L\.L\.C\.|Corp\.?|Corporation|Company|Co\.|Pvt\.?\s*Ltd\.?|"
    r"Gmbh|S\.A\.|plc|Bank|University|College|Institute|Foundation|Ministry|Department|"
    r"Agency|Authority|Organization|Organisation|Group|Ventures|Enterprises|Solutions))\b"
)

# Minimal English honorific-free stopword guard for person names.
_NAME_STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "date", "name", "number",
    "invoice", "receipt", "total", "amount", "page", "document", "signature",
}

# Organisations captured by a person label must not be reported as people.
_ORG_SUFFIX_RE = re.compile(
    r"\b(?:inc|ltd|llc|corp|corporation|company|co|gmbh|plc|pvt|limited|bank|"
    r"university|college|institute|foundation|ministry|department|agency|authority)\b\.?$",
    re.IGNORECASE,
)


def _normalize_date(raw: str, kind: str) -> str | None:
    raw = raw.strip().rstrip(",")
    candidates = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y", "%d %B, %Y", "%B %d, %Y"]
    if kind == "iso":
        candidates = ["%Y-%m-%d"] + candidates
    for fmt in candidates:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _normalize_money(raw: str) -> str | None:
    cleaned = re.sub(r"[^\d.,]", "", raw)
    cleaned = cleaned.replace(",", "")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return f"{value:.2f}"


def _context(line: str, start: int, end: int, pad: int = 60) -> str:
    lo, hi = max(0, start - pad), min(len(line), end + pad)
    return line[lo:hi].strip()


def _phone_plausible(raw: str) -> bool:
    digits = re.sub(r"\D", "", raw)
    return 7 <= len(digits) <= 15


def extract_entities(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract entities page by page from extraction ``pages`` entries."""
    hits: list[tuple[int, EntityHit]] = []
    seen: set[tuple[str, str, int]] = set()

    def add(hit: EntityHit, page_number: int) -> None:
        key = (hit.entity_type, (hit.normalized_value or hit.value).lower(), page_number)
        if key in seen:
            return
        seen.add(key)
        hits.append((page_number, hit))

    for page in pages:
        page_number = int(page.get("page_number") or 0)
        text = page.get("text") or ""
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            for match in _URL_RE.finditer(stripped):
                add(
                    EntityHit(
                        "url",
                        match.group(0),
                        match.group(0).lower(),
                        0.95,
                        _context(stripped, *match.span()),
                        match.span(),
                    ),
                    page_number,
                )

            for match in _EMAIL_RE.finditer(stripped):
                add(
                    EntityHit(
                        "email",
                        match.group(0),
                        match.group(0).lower(),
                        0.98,
                        _context(stripped, *match.span()),
                        match.span(),
                    ),
                    page_number,
                )

            for match in _MONEY_RE.finditer(stripped):
                add(
                    EntityHit(
                        "money",
                        match.group(0),
                        _normalize_money(match.group(0)),
                        0.9,
                        _context(stripped, *match.span()),
                        match.span(),
                    ),
                    page_number,
                )

            for pattern, kind in _DATE_PATTERNS:
                for match in pattern.finditer(stripped):
                    add(
                        EntityHit(
                            "date",
                            match.group(1),
                            _normalize_date(match.group(1), kind),
                            0.9 if kind == "iso" else 0.8,
                            _context(stripped, match.start(1), match.end(1)),
                            (match.start(1), match.end(1)),
                        ),
                        page_number,
                    )

            for match in _IDENTIFIER_RE.finditer(stripped):
                value = match.group(1).strip()
                if len(re.sub(r"[^A-Za-z0-9]", "", value)) < 5:
                    continue
                add(
                    EntityHit(
                        "document_identifier",
                        value,
                        value.upper(),
                        0.75,
                        _context(stripped, *match.span()),
                        match.span(),
                    ),
                    page_number,
                )

            for match in _PHONE_RE.finditer(stripped):
                raw = match.group(0)
                if not _phone_plausible(raw) or _EMAIL_RE.search(raw):
                    continue
                add(
                    EntityHit(
                        "phone",
                        raw,
                        re.sub(r"\D", "", raw),
                        0.7,
                        _context(stripped, *match.span()),
                        match.span(),
                    ),
                    page_number,
                )

            for match in _PERSON_LABEL_RE.finditer(stripped):
                name = match.group(1).strip()
                if name.split()[0].lower() in _NAME_STOPWORDS:
                    continue
                if _ORG_SUFFIX_RE.search(name):
                    continue
                add(
                    EntityHit(
                        "person_name",
                        name,
                        " ".join(name.lower().split()),
                        0.85,
                        _context(stripped, *match.span()),
                        match.span(),
                    ),
                    page_number,
                )

            for match in _PERSON_TITLE_RE.finditer(stripped):
                name = match.group(1).strip()
                add(
                    EntityHit(
                        "person_name",
                        name,
                        " ".join(name.lower().split()),
                        0.75,
                        _context(stripped, *match.span()),
                        match.span(),
                    ),
                    page_number,
                )

            for match in _ORG_RE.finditer(stripped):
                name = match.group(1).strip()
                if len(name.split()) < 2:
                    continue
                add(
                    EntityHit(
                        "organization",
                        name,
                        " ".join(name.lower().split()),
                        0.8,
                        _context(stripped, *match.span()),
                        match.span(),
                    ),
                    page_number,
                )

    return [
        {
            "entity_type": hit.entity_type,
            "value": hit.value,
            "normalized_value": hit.normalized_value,
            "confidence": hit.confidence,
            "page_number": page_number,
            "source_text": hit.source_text,
        }
        for page_number, hit in hits
    ]


def summarize_entities(entities: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entity in entities:
        counts[entity["entity_type"]] = counts.get(entity["entity_type"], 0) + 1
    return counts
