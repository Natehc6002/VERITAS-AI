"""Document management endpoints."""

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.deps import CurrentUser, DbSession
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
    401: {"model": ErrorResponse, "description": "Missing or invalid access token."},
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
        "filename is used, and basic PDF metadata (page count, document info) is extracted. "
        "Optionally provide an investigation_id owned by the authenticated user."
    ),
    responses=_ERROR_RESPONSES,
)
def upload_document(
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(..., description="PDF, PNG, JPG or JPEG file."),
    investigation_id: str | None = Form(
        default=None, description="Owned investigation to file the document under."
    ),
) -> Document:
    return document_service.upload_document(db, file, user, investigation_id)


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents",
    description=(
        "Return the authenticated user's documents, newest first, with pagination, "
        "case-insensitive filename search and optional investigation filtering."
    ),
    responses=_ERROR_RESPONSES,
)
def list_documents(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1, description="Page number (1-based)."),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)."),
    search: str | None = Query(
        None,
        max_length=200,
        description="Case-insensitive substring to match against the original filename.",
    ),
    investigation_id: str | None = Query(
        None, description="Only return documents filed under this investigation."
    ),
) -> DocumentListResponse:
    return document_service.list_documents(
        db,
        user,
        page=page,
        page_size=page_size,
        search=search,
        investigation_id=investigation_id,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document details",
    description="Return the complete available metadata for a single owned document.",
    responses=_ERROR_RESPONSES,
)
def get_document(
    document_id: str,
    db: DbSession,
    user: CurrentUser,
) -> Document:
    return document_service.get_document(db, document_id, user)


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
    db: DbSession,
    user: CurrentUser,
) -> MessageResponse:
    document_service.delete_document(db, document_id, user)
    return MessageResponse(message="Document deleted successfully.")
