"""Forensic investigation report generation (PDF via PyMuPDF, already a dependency)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pymupdf as fitz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.intelligence import (
    AnalysisStatus,
    DocumentAnalysis,
    Entity,
    Evidence,
    Finding,
    TextExtraction,
)
from app.models.user import User
from app.services import analysis_service, cross_document, investigation_service

logger = logging.getLogger(__name__)

PAGE_W, PAGE_H = fitz.paper_size("a4")
MARGIN = 54
CONTENT_W = PAGE_W - 2 * MARGIN

FONT = "helv"
FONT_BOLD = "hebo"

BLACK = (0.1, 0.1, 0.1)
GREY = (0.45, 0.45, 0.45)
ACCENT = (0.09, 0.29, 0.53)
SEVERITY_COLORS = {
    "high": (0.72, 0.11, 0.11),
    "medium": (0.80, 0.45, 0.05),
    "low": (0.20, 0.45, 0.20),
}


class _PdfBuilder:
    """Minimal paginating text layout engine on top of PyMuPDF."""

    def __init__(self) -> None:
        self.doc = fitz.open()
        self.page: fitz.Page | None = None
        self.y = MARGIN
        self._new_page()

    def _new_page(self) -> None:
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.y = MARGIN

    def _ensure(self, height: float) -> None:
        if self.y + height > PAGE_H - MARGIN:
            self._new_page()

    @staticmethod
    def _wrap(text: str, size: float, font: str, width: float) -> list[str]:
        lines: list[str] = []
        for raw_line in text.splitlines() or [""]:
            words = raw_line.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                candidate = f"{current} {word}"
                if fitz.get_text_length(candidate, fontname=font, fontsize=size) <= width:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines

    def text(
        self,
        value: str,
        size: float = 9.5,
        font: str = FONT,
        color: tuple[float, float, float] = BLACK,
        indent: float = 0,
        gap: float = 4,
        leading: float = 1.35,
    ) -> None:
        width = CONTENT_W - indent
        lines = self._wrap(str(value), size, font, width)
        line_h = size * leading
        for line in lines:
            self._ensure(line_h)
            assert self.page is not None
            self.page.insert_text(
                (MARGIN + indent, self.y + size),
                line,
                fontname=font,
                fontsize=size,
                color=color,
            )
            self.y += line_h
        self.y += gap

    def heading(self, value: str, level: int = 1) -> None:
        size = {1: 15, 2: 12, 3: 10.5}[level]
        gap_before = {1: 6, 2: 12, 3: 8}[level]
        self.y += gap_before
        self._ensure(size * 2)
        self.text(value, size=size, font=FONT_BOLD, color=ACCENT if level <= 2 else BLACK, gap=6)
        if level == 1:
            assert self.page is not None
            self.page.draw_line(
                (MARGIN, self.y), (PAGE_W - MARGIN, self.y), color=ACCENT, width=1
            )
            self.y += 8

    def bullet(self, value: str, color: tuple[float, float, float] = BLACK) -> None:
        self.text(f"•  {value}", color=color, indent=10, gap=2)

    def key_value(self, key: str, value: Any) -> None:
        self.text(f"{key}:  {value}", size=9, color=GREY, gap=1)

    def spacer(self, points: float = 8) -> None:
        self.y += points

    def page_break(self) -> None:
        self._new_page()

    def output(self) -> bytes:
        total = len(self.doc)
        for index, page in enumerate(self.doc, start=1):
            footer = f"VERITAS AI · Forensic Investigation Report · page {index}/{total}"
            page.insert_text(
                (MARGIN, PAGE_H - 28),
                footer,
                fontname=FONT,
                fontsize=7.5,
                color=GREY,
            )
        data = self.doc.tobytes(garbage=4, deflate=True)
        self.doc.close()
        return data


def build_investigation_report(
    db: Session, user: User, investigation_id: str
) -> tuple[bytes, str]:
    """Build the PDF report for an owned investigation. Returns (pdf_bytes, filename)."""
    investigation = investigation_service.get_investigation(db, user, investigation_id)
    documents = list(
        db.scalars(
            select(Document)
            .where(
                Document.investigation_id == investigation.id,
                Document.owner_id == user.id,
            )
            .order_by(Document.upload_timestamp.asc())
        ).all()
    )

    # Ensure analyses exist so entities/findings/comparisons are available.
    for document in documents:
        analysis_service.get_or_run_analysis(db, document)

    comparison: dict[str, Any] | None = None
    if len(documents) >= 2:
        try:
            comparison = cross_document.compare_documents(
                db, [doc.id for doc in documents]
            )
        except Exception:  # noqa: BLE001 - report must still generate
            logger.exception("Comparison section failed for investigation %s", investigation.id)

    builder = _PdfBuilder()
    _cover(builder, investigation, user, documents)
    _document_section(builder, db, documents)
    if comparison is not None:
        _comparison_section(builder, comparison)
    _disclaimer(builder)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"veritas-report-{investigation.name[:24].strip() or 'report'}-{stamp}.pdf"
    filename = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in filename)
    return builder.output(), filename


def _cover(builder: _PdfBuilder, investigation, user: User, documents: list[Document]) -> None:
    builder.spacer(30)
    builder.text("VERITAS AI", size=11, font=FONT_BOLD, color=ACCENT, gap=2)
    builder.text(
        "Forensic Investigation Report", size=22, font=FONT_BOLD, color=BLACK, gap=14
    )
    builder.heading(investigation.name, level=2)
    if investigation.description:
        builder.text(investigation.description, size=10, color=GREY, gap=10)
    builder.key_value("Investigation ID", investigation.id)
    builder.key_value("Prepared for", user.email)
    builder.key_value(
        "Generated (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    )
    builder.key_value("Documents in scope", len(documents))
    builder.key_value("Created", investigation.created_at.strftime("%Y-%m-%d %H:%M UTC"))
    builder.spacer(6)
    builder.text(
        "This report aggregates explainable forensic indicators, extracted entities, "
        "supporting evidence and cross-document observations. Indicators are not "
        "determinations of fraud or tampering.",
        size=9,
        color=GREY,
    )


def _document_section(builder: _PdfBuilder, db: Session, documents: list[Document]) -> None:
    builder.page_break()
    builder.heading("1. Document information", level=1)
    if not documents:
        builder.text("No documents are filed under this investigation.", color=GREY)
        return

    for index, document in enumerate(documents, start=1):
        builder.heading(f"1.{index}  {document.original_filename}", level=3)
        builder.key_value("Document ID", document.id)
        builder.key_value("Type / size", f"{document.file_extension.upper()} · {document.file_size} bytes")
        builder.key_value("SHA-256", document.sha256_hash)
        builder.key_value(
            "Uploaded",
            document.upload_timestamp.strftime("%Y-%m-%d %H:%M UTC"),
        )
        if document.page_count:
            builder.key_value("Pages", document.page_count)

        analysis = db.scalar(
            select(DocumentAnalysis).where(DocumentAnalysis.document_id == document.id)
        )
        if analysis and analysis.status == AnalysisStatus.COMPLETED.value:
            label = (analysis.category or "other").replace("_", " ").title()
            builder.key_value(
                "Classification",
                f"{label} ({(analysis.category_confidence or 0):.0%} confidence)",
            )
        extraction = db.scalar(
            select(TextExtraction).where(TextExtraction.document_id == document.id)
        )
        if extraction:
            builder.key_value(
                "Text extraction",
                f"{extraction.status} · {extraction.word_count or 0} words · "
                f"{extraction.page_count or 0} page(s)",
            )

        _entities(builder, db, document)
        _findings(builder, db, document)
        builder.spacer(6)


def _entities(builder: _PdfBuilder, db: Session, document: Document) -> None:
    entities = list(
        db.scalars(
            select(Entity)
            .where(Entity.document_id == document.id)
            .order_by(Entity.entity_type.asc())
        ).all()
    )
    builder.heading("Extracted entities", level=3)
    if not entities:
        builder.text("No entities were extracted.", color=GREY, indent=10)
        return
    for entity in entities[:80]:
        page = f" · p.{entity.page_number}" if entity.page_number else ""
        builder.bullet(
            f"{entity.entity_type.replace('_', ' ')}: {entity.value} "
            f"({entity.confidence:.0%}{page})"
        )
    if len(entities) > 80:
        builder.bullet(f"… {len(entities) - 80} further entities omitted.")


def _findings(builder: _PdfBuilder, db: Session, document: Document) -> None:
    findings = list(
        db.scalars(
            select(Finding)
            .where(Finding.document_id == document.id)
            .order_by(Finding.severity.asc(), Finding.category.asc())
        ).all()
    )
    builder.heading("Forensic findings and evidence", level=3)
    if not findings:
        builder.text("No forensic indicators were raised.", color=GREY, indent=10)
        return

    for finding in findings:
        color = SEVERITY_COLORS.get(finding.severity, BLACK)
        builder.text(
            f"[{finding.severity.upper()}]  {finding.title}",
            size=9.5,
            font=FONT_BOLD,
            color=color,
            gap=2,
        )
        builder.text(finding.explanation or "", size=9, indent=10, gap=2)
        builder.text(
            f"Category: {finding.category} · Confidence: {finding.confidence:.0%} · "
            f"Method: {finding.detection_method}"
            + (f" · Page: {finding.page_number}" if finding.page_number else ""),
            size=8,
            color=GREY,
            indent=10,
            gap=3,
        )

        evidence_rows = list(
            db.scalars(
                select(Evidence)
                .where(
                    Evidence.document_id == document.id,
                    Evidence.finding_id == finding.id,
                )
                .order_by(Evidence.page_number.asc())
            ).all()
        )
        for item in evidence_rows:
            builder.text(
                f"· Evidence [{item.evidence_type}] source: {item.source_ref or 'n/a'}"
                + (f" (page {item.page_number})" if item.page_number else ""),
                size=8,
                font=FONT_BOLD,
                color=GREY,
                indent=18,
                gap=1,
            )
            if item.excerpt:
                builder.text(f"“{item.excerpt[:400]}”", size=8, color=GREY, indent=26, gap=1)
            if item.explanation:
                builder.text(item.explanation, size=8, color=GREY, indent=26, gap=3)
        builder.spacer(4)


def _comparison_section(builder: _PdfBuilder, comparison: dict[str, Any]) -> None:
    builder.page_break()
    builder.heading("2. Cross-document comparison", level=1)
    names = ", ".join(comparison.get("document_names") or [])
    builder.text(f"Documents compared: {names}", size=9.5, gap=6)

    shared = comparison.get("shared_entities") or []
    builder.heading("Shared entities", level=2)
    if not shared:
        builder.text("No shared normalized entity values were found.", color=GREY)
    for item in shared[:40]:
        docs = ", ".join(item.get("document_names") or [])
        builder.bullet(f"{item.get('entity_type', '')}: {item.get('value', '')} — {docs}")
    if len(shared) > 40:
        builder.bullet(f"… {len(shared) - 40} further shared entities omitted.")

    conflicts = comparison.get("conflicts") or []
    builder.heading("Detected conflicts", level=2)
    if not conflicts:
        builder.text("No conflicts were detected between the compared documents.", color=GREY)
    for item in conflicts[:30]:
        builder.text(
            f"[{item.get('severity', 'info').upper()}] {item.get('title', '')}",
            size=9.5,
            font=FONT_BOLD,
            color=SEVERITY_COLORS.get(str(item.get("severity", "")), BLACK),
            gap=1,
        )
        builder.text(item.get("explanation", ""), size=9, indent=10, gap=4)

    related = comparison.get("related_records") or []
    if related:
        builder.heading("Related records", level=2)
        for item in related[:30]:
            builder.bullet(str(item.get("title") or item))

    summary = comparison.get("summary") or {}
    builder.spacer(4)
    builder.text(
        f"Summary: {summary.get('documents_compared', 0)} document(s), "
        f"{summary.get('shared_entity_count', 0)} shared entities, "
        f"{summary.get('related_record_count', 0)} related record pair(s), "
        f"{summary.get('conflict_count', 0)} conflict(s).",
        size=9,
        color=GREY,
    )
    builder.text(str(comparison.get("disclaimer") or ""), size=8, color=GREY)


def _disclaimer(builder: _PdfBuilder) -> None:
    builder.spacer(10)
    builder.heading("3. Methodology and limitations", level=1)
    builder.text(
        "Classification uses a deterministic rule-based baseline. Entities and "
        "indicators are derived from PDF metadata and extracted text (native "
        "extraction or OCR). Every indicator is presented with its evidence and "
        "source reference so a human reviewer can verify it. Shared or conflicting "
        "values across documents are observations, not proof of fraud.",
        size=9,
    )
    builder.text(
        "Generated by VERITAS AI · indicators require human review · "
        "not an automated fraud verdict.",
        size=8,
        color=GREY,
    )
