"""Pydantic response/request models for extraction, analysis and comparison."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PageTextResponse(BaseModel):
    page_number: int
    text: str
    char_count: int
    word_count: int
    method: str
    confidence: float | None = None


class ExtractionResponse(BaseModel):
    document_id: str
    status: str
    method: str
    page_count: int | None = None
    char_count: int = 0
    word_count: int = 0
    ocr_available: bool = False
    error: str | None = None
    pages: list[PageTextResponse] = Field(default_factory=list)


class EntityResponse(BaseModel):
    id: str
    entity_type: str
    value: str
    normalized_value: str | None = None
    confidence: float | None = None
    page_number: int | None = None
    source_text: str | None = None


class EvidenceResponse(BaseModel):
    id: str
    page_number: int | None = None
    evidence_type: str
    source_ref: str
    excerpt: str | None = None
    explanation: str


class FindingResponse(BaseModel):
    id: str
    category: str
    severity: str
    confidence: float | None = None
    title: str
    explanation: str
    detection_method: str
    page_number: int | None = None
    created_at: datetime | None = None
    evidence: list[EvidenceResponse] = Field(default_factory=list)


class ClassificationResponse(BaseModel):
    status: str
    category: str | None = None
    category_label: str | None = None
    confidence: float | None = None
    rationale: list[dict[str, Any]] = Field(default_factory=list)
    method: str | None = None


class AnalysisResponse(BaseModel):
    document_id: str
    extraction: ExtractionResponse | None = None
    classification: ClassificationResponse
    summary: str | None = None
    entities: list[EntityResponse] = Field(default_factory=list)
    findings: list[FindingResponse] = Field(default_factory=list)
    disclaimer: str | None = None


class CompareRequest(BaseModel):
    document_ids: list[str] = Field(
        min_length=2, max_length=25, description="Two or more document ids to compare."
    )

    @field_validator("document_ids")
    @classmethod
    def _strip_duplicates(cls, value: list[str]) -> list[str]:
        seen: list[str] = []
        for item in value:
            if item not in seen:
                seen.append(item)
        if len(seen) < 2:
            raise ValueError("At least two distinct document ids are required.")
        return seen


class SharedEntityOccurrence(BaseModel):
    document_id: str
    document_name: str
    page_number: int | None = None
    source_text: str | None = None
    confidence: float | None = None


class SharedEntity(BaseModel):
    entity_type: str
    value: str
    normalized_value: str
    document_count: int
    occurrences: list[SharedEntityOccurrence]
    explanation: str


class RelatedRecord(BaseModel):
    document_ids: list[str]
    document_names: list[str]
    shared_values: list[dict[str, Any]]
    explanation: str


class ConflictValue(BaseModel):
    value: str
    documents: list[dict[str, Any]]


class Conflict(BaseModel):
    conflict_type: str
    field: str
    subject: str | None = None
    values: list[ConflictValue]
    explanation: str
    severity: str


class CompareResponse(BaseModel):
    document_ids: list[str]
    document_names: list[str]
    shared_entities: list[SharedEntity]
    related_records: list[RelatedRecord]
    conflicts: list[Conflict]
    summary: dict[str, Any]
    method: str
    disclaimer: str


class RecentDocument(BaseModel):
    id: str
    original_filename: str
    file_extension: str
    upload_timestamp: datetime
    processing_status: str
    file_size: int


class StatsResponse(BaseModel):
    total_documents: int
    processed_documents: int
    failed_documents: int
    documents_with_text: int
    total_findings: int
    findings_by_severity: dict[str, int]
    total_entities: int
    recent_documents: list[RecentDocument]
