"""ORM models for text extraction, understanding, findings and evidence."""

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExtractionMethod(StrEnum):
    NATIVE = "native"
    OCR = "ocr"
    NONE = "none"


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    NO_TEXT = "no_text"
    FAILED = "failed"


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class TextExtraction(Base):
    """Text extraction result for a document (1:1)."""

    __tablename__ = "text_extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ExtractionStatus.PENDING.value
    )
    method: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ExtractionMethod.NONE.value
    )
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    pages: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ocr_available: Mapped[bool] = mapped_column(nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class DocumentAnalysis(Base):
    """Classification and summary result for a document (1:1)."""

    __tablename__ = "document_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AnalysisStatus.PENDING.value
    )
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category_confidence: Mapped[float | None] = mapped_column(nullable=True)
    category_rationale: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class Entity(Base):
    """An entity extracted from a document's text."""

    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class Finding(Base):
    """An explainable forensic indicator raised for a document."""

    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    detection_method: Mapped[str] = mapped_column(String(100), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    evidence_items: Mapped[list["Evidence"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )


class Evidence(Base):
    """Source trace supporting a finding (or a document-level observation)."""

    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("findings.id", ondelete="CASCADE"), nullable=True, index=True
    )
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(300), nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    finding: Mapped[Finding | None] = relationship(back_populates="evidence_items")
