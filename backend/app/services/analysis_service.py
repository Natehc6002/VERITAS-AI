"""Analysis orchestration: extraction -> classification -> entities -> findings."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import DocumentNotFoundError, VeritasError
from app.models.document import Document
from app.models.intelligence import (
    AnalysisStatus,
    DocumentAnalysis,
    Entity,
    Evidence,
    ExtractionStatus,
    Finding,
    TextExtraction,
)
from app.models.user import User
from app.services import classification, entity_extraction, forensics, text_extraction

logger = logging.getLogger(__name__)


class AnalysisNotPossibleError(VeritasError):
    status_code = 409


def run_analysis(db: Session, document: Document, force: bool = False) -> dict[str, Any]:
    """Run the full single-document analysis pipeline and persist every stage."""
    extraction = text_extraction.get_extraction(db, document)
    if extraction is None or force:
        extraction = text_extraction.extract_document_text(db, document)

    text = extraction.full_text or ""
    classification_result = classification.classify_text(text, document.original_filename)

    entities = _persist_entities(db, document, extraction)
    findings = _persist_findings(db, document, extraction)
    summary = _build_summary(document, extraction, classification_result, entities, findings)

    analysis = db.query(DocumentAnalysis).filter(DocumentAnalysis.document_id == document.id).first()
    if analysis is None:
        analysis = DocumentAnalysis(document_id=document.id)
        db.add(analysis)
    analysis.status = AnalysisStatus.COMPLETED.value
    analysis.category = classification_result["category"]
    analysis.category_confidence = classification_result["confidence"]
    analysis.category_rationale = classification_result["rationale"]
    analysis.summary = summary
    analysis.error = None
    db.commit()

    return build_analysis_bundle(db, document)


def build_analysis_bundle(db: Session, document: Document) -> dict[str, Any]:
    """Assemble the full analysis payload for API responses."""
    extraction = text_extraction.get_extraction(db, document)
    analysis = db.query(DocumentAnalysis).filter(DocumentAnalysis.document_id == document.id).first()
    entities = list(
        db.scalars(select(Entity).where(Entity.document_id == document.id)).all()
    )
    findings = list(
        db.scalars(select(Finding).where(Finding.document_id == document.id)).all()
    )
    evidence = list(
        db.scalars(select(Evidence).where(Evidence.document_id == document.id)).all()
    )

    evidence_by_finding: dict[str, list[Any]] = {}
    for item in evidence:
        if item.finding_id:
            evidence_by_finding.setdefault(item.finding_id, []).append(item)

    return {
        "document_id": document.id,
        "extraction": _extraction_payload(document, extraction),
        "classification": (
            {
                "status": analysis.status,
                "category": analysis.category,
                "category_label": classification.CATEGORIES.get(
                    analysis.category or "other", "Other"
                ),
                "confidence": analysis.category_confidence,
                "rationale": analysis.category_rationale or [],
                "method": "rule_based_baseline",
            }
            if analysis
            else {"status": AnalysisStatus.PENDING.value}
        ),
        "summary": analysis.summary if analysis else None,
        "entities": [
            {
                "id": entity.id,
                "entity_type": entity.entity_type,
                "value": entity.value,
                "normalized_value": entity.normalized_value,
                "confidence": entity.confidence,
                "page_number": entity.page_number,
                "source_text": entity.source_text,
            }
            for entity in entities
        ],
        "findings": [
            {
                "id": finding.id,
                "category": finding.category,
                "severity": finding.severity,
                "confidence": finding.confidence,
                "title": finding.title,
                "explanation": finding.explanation,
                "detection_method": finding.detection_method,
                "page_number": finding.page_number,
                "created_at": finding.created_at,
                "evidence": [
                    {
                        "id": item.id,
                        "page_number": item.page_number,
                        "evidence_type": item.evidence_type,
                        "source_ref": item.source_ref,
                        "excerpt": item.excerpt,
                        "explanation": item.explanation,
                    }
                    for item in evidence_by_finding.get(finding.id, [])
                ],
            }
            for finding in findings
        ],
        "disclaimer": (
            "Findings are explainable indicators derived from metadata and extracted "
            "text. An indicator is not a determination of fraud or tampering."
        ),
    }


def get_or_run_analysis(db: Session, document: Document) -> dict[str, Any]:
    analysis = db.query(DocumentAnalysis).filter(DocumentAnalysis.document_id == document.id).first()
    extraction = text_extraction.get_extraction(db, document)
    if analysis is None or extraction is None:
        return run_analysis(db, document)
    return build_analysis_bundle(db, document)


def delete_analysis_rows(db: Session, document_id: str) -> None:
    """Remove all intelligence rows for a document (used before re-analysis/deletion)."""
    for model in (Entity, Finding, Evidence, DocumentAnalysis, TextExtraction):
        db.query(model).filter(model.document_id == document_id).delete(synchronize_session=False)


def _persist_entities(db: Session, document: Document, extraction: TextExtraction) -> list[Entity]:
    rows = entity_extraction.extract_entities(extraction.pages or [])
    db.query(Entity).filter(Entity.document_id == document.id).delete(synchronize_session=False)
    entities = [
        Entity(
            document_id=document.id,
            entity_type=row["entity_type"],
            value=row["value"][:500],
            normalized_value=(row["normalized_value"] or "")[:500] or None,
            confidence=row["confidence"],
            page_number=row["page_number"],
            source_text=(row["source_text"] or "")[:1000] or None,
        )
        for row in rows
    ]
    for entity in entities:
        db.add(entity)
    db.commit()
    return entities


def _persist_findings(db: Session, document: Document, extraction: TextExtraction) -> list[Finding]:
    duplicate_of = (
        db.query(Document)
        .filter(
            Document.sha256_hash == document.sha256_hash,
            Document.id != document.id,
            Document.owner_id == document.owner_id,
        )
        .first()
    )
    finding_dicts = forensics.analyze_document(document, extraction, duplicate_of=duplicate_of)

    db.query(Evidence).filter(Evidence.document_id == document.id).delete(synchronize_session=False)
    db.query(Finding).filter(Finding.document_id == document.id).delete(synchronize_session=False)
    db.commit()

    findings: list[Finding] = []
    for item in finding_dicts:
        finding = Finding(
            document_id=document.id,
            category=item["category"],
            severity=item["severity"],
            confidence=item["confidence"],
            title=item["title"],
            explanation=item["explanation"],
            detection_method=item["detection_method"],
            page_number=item["page_number"],
        )
        db.add(finding)
        db.flush()
        for ev in item["evidence"]:
            db.add(
                Evidence(
                    document_id=document.id,
                    finding_id=finding.id,
                    page_number=ev.get("page_number"),
                    evidence_type=ev["evidence_type"],
                    source_ref=ev["source_ref"],
                    excerpt=(ev.get("excerpt") or "")[:2000] or None,
                    explanation=ev["explanation"],
                )
            )
        findings.append(finding)
    db.commit()
    return findings


def _build_summary(
    document: Document,
    extraction: TextExtraction,
    classification_result: dict[str, Any],
    entities: list[Entity],
    findings: list[Finding],
) -> str:
    """Deterministic factual summary built only from extracted data."""
    parts: list[str] = []
    label = classification_result.get("category_label", "Other")
    parts.append(
        f"'{document.original_filename}' is classified as {label} "
        f"(rule-based baseline, confidence {classification_result.get('confidence', 0):.0%})."
    )

    if extraction.status == ExtractionStatus.COMPLETED.value:
        method_label = (
            "native PDF text extraction"
            if extraction.method == "native"
            else "OCR"
        )
        parts.append(
            f"Text was extracted via {method_label} from {extraction.page_count or 0} "
            f"page(s): {extraction.word_count} words / {extraction.char_count} characters."
        )
    elif extraction.status == ExtractionStatus.NO_TEXT.value:
        parts.append(
            "No usable text layer was found, so content analysis is limited to metadata."
        )
    elif extraction.status == ExtractionStatus.FAILED.value:
        parts.append(f"Text extraction failed: {extraction.error or 'unknown error'}.")

    counts = entity_extraction.summarize_entities(
        [{"entity_type": e.entity_type} for e in entities]
    )
    if counts:
        rendered = ", ".join(
            f"{count} {etype.replace('_', ' ')}" for etype, count in sorted(counts.items())
        )
        parts.append(f"Extracted entities: {rendered}.")
    else:
        parts.append("No entities were extracted from the available text.")

    if findings:
        severity_counts: dict[str, int] = {}
        for finding in findings:
            severity_counts[finding.severity] = severity_counts.get(finding.severity, 0) + 1
        rendered = ", ".join(
            f"{count} {severity}" for severity, count in sorted(severity_counts.items())
        )
        parts.append(
            f"{len(findings)} forensic indicator(s) raised ({rendered}). "
            "Indicators require human review and are not determinations of fraud."
        )
    else:
        parts.append("No forensic indicators were raised for this document.")

    return " ".join(parts)


def _extraction_payload(document: Document, extraction: TextExtraction | None) -> dict[str, Any] | None:
    if extraction is None:
        return None
    return {
        "document_id": document.id,
        "status": extraction.status,
        "method": extraction.method,
        "page_count": extraction.page_count,
        "char_count": extraction.char_count,
        "word_count": extraction.word_count,
        "ocr_available": extraction.ocr_available,
        "error": extraction.error,
        "pages": extraction.pages or [],
    }


def document_stats(db: Session, user: User) -> dict[str, Any]:
    """Dashboard statistics derived from real database rows, scoped to ``user``."""
    owned_documents = select(Document.id).where(Document.owner_id == user.id)

    total = db.scalar(select(func.count()).select_from(Document).where(Document.owner_id == user.id)) or 0
    by_status = dict(
        db.execute(
            select(Document.processing_status, func.count())
            .where(Document.owner_id == user.id)
            .group_by(Document.processing_status)
        ).all()
    )
    recent = list(
        db.scalars(
            select(Document)
            .where(Document.owner_id == user.id)
            .order_by(Document.upload_timestamp.desc())
            .limit(5)
        ).all()
    )
    findings_total = (
        db.scalar(
            select(func.count())
            .select_from(Finding)
            .where(Finding.document_id.in_(owned_documents))
        )
        or 0
    )
    findings_by_severity = dict(
        db.execute(
            select(Finding.severity, func.count())
            .where(Finding.document_id.in_(owned_documents))
            .group_by(Finding.severity)
        ).all()
    )
    entities_total = (
        db.scalar(
            select(func.count())
            .select_from(Entity)
            .where(Entity.document_id.in_(owned_documents))
        )
        or 0
    )
    extractions_completed = (
        db.scalar(
            select(func.count())
            .select_from(TextExtraction)
            .where(
                TextExtraction.status == ExtractionStatus.COMPLETED.value,
                TextExtraction.document_id.in_(owned_documents),
            )
        )
        or 0
    )

    return {
        "total_documents": total,
        "processed_documents": by_status.get("completed", 0),
        "failed_documents": by_status.get("failed", 0),
        "documents_with_text": extractions_completed,
        "total_findings": findings_total,
        "findings_by_severity": findings_by_severity,
        "total_entities": entities_total,
        "recent_documents": [
            {
                "id": doc.id,
                "original_filename": doc.original_filename,
                "file_extension": doc.file_extension,
                "upload_timestamp": doc.upload_timestamp,
                "processing_status": doc.processing_status,
                "file_size": doc.file_size,
            }
            for doc in recent
        ],
    }


def require_document(db: Session, document_id: str, user: User) -> Document:
    """Return the document only when it exists and belongs to ``user``."""
    document = db.get(Document, str(document_id)) if _is_uuid(document_id) else None
    if document is None or document.owner_id != user.id:
        raise DocumentNotFoundError("Document not found.")
    return document


def _is_uuid(value: str) -> bool:
    from uuid import UUID

    try:
        UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False
