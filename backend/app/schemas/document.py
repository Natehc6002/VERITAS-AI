"""Pydantic request/response models for document endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    """Public metadata of an uploaded document."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    original_filename: str
    file_extension: str
    mime_type: str
    file_size: int
    sha256_hash: str
    upload_timestamp: datetime
    processing_status: str
    page_count: int | None = None
    pdf_metadata: dict[str, Any] | None = None
    investigation_id: str | None = None


class DocumentListResponse(BaseModel):
    """Paginated document listing."""

    items: list[DocumentResponse]
    total: int = Field(description="Total number of matching documents.")
    page: int = Field(description="Current page number (1-based).")
    page_size: int = Field(description="Maximum items per page.")


class HealthResponse(BaseModel):
    status: str


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
