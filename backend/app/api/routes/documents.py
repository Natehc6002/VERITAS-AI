"""Document management endpoints."""

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.document import Document
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    ErrorResponse,
    MessageResponse,
)
from app.services import document_service

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

_ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    400: {"model": ErrorResponse, "description": "Invalid file content or empty upload."},
    404: {"model": ErrorResponse, "description": "Document not found."},
    413: {"model": ErrorResponse, "description": "File exceeds the size limit."},
    415: {"model": ErrorResponse, "description": "Unsupported file type."},
    500: {"model": ErrorResponse, "description": "Storage or database failure."},
}


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    description=(
        "Upload a PDF, PNG, JPG or JPEG file (max 20 MB by default). "
        "The file signature is verified server-side, a unique server-generated "
        "filename is used, and basic PDF metadata (page count, document info) is extracted."
    ),
    responses=_ERROR_RESPONSES,
)
def upload_document(
    file: UploadFile = File(..., description="PDF, PNG, JPG or JPEG file."),
    db: Session = Depends(get_db),
) -> Document:
    return document_service.upload_document(db, file)


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents",
    description=(
        "Return uploaded documents, newest first, with pagination and "
        "case-insensitive filename search."
    ),
    responses=_ERROR_RESPONSES,
)
def list_documents(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-based)."),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)."),
    search: str | None = Query(
        None,
        max_length=200,
        description="Case-insensitive substring to match against the original filename.",
    ),
) -> DocumentListResponse:
    return document_service.list_documents(db, page=page, page_size=page_size, search=search)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details",
    description="Return the complete available metadata for a single document.",
    responses=_ERROR_RESPONSES,
)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
) -> Document:
    return document_service.get_document(db, document_id)


@router.delete(
    "/{document_id}",
    response_model=MessageResponse,
    summary="Delete a document",
    description=(
        "Delete the document record and its stored file. "
        "Missing files are tolerated to keep database and filesystem consistent."
    ),
    responses=_ERROR_RESPONSES,
)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
) -> MessageResponse:
    document_service.delete_document(db, document_id)
    return MessageResponse(message="Document deleted successfully.")
