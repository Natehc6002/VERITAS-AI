"""Text extraction endpoints."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.models.document import Document
from app.schemas.intelligence import ExtractionResponse
from app.services import analysis_service, text_extraction

router = APIRouter(prefix="/api/v1/documents", tags=["extraction"])


def _extraction_response(document: Document, extraction) -> ExtractionResponse:
    return ExtractionResponse(
        document_id=document.id,
        status=extraction.status,
        method=extraction.method,
        page_count=extraction.page_count,
        char_count=extraction.char_count,
        word_count=extraction.word_count,
        ocr_available=extraction.ocr_available,
        error=extraction.error,
        pages=extraction.pages or [],
    )


@router.post(
    "/{document_id}/extract",
    response_model=ExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract text from a document",
    description=(
        "Run (or re-run) text extraction. PDFs use native PyMuPDF extraction; "
        "scanned PDFs and images fall back to OCR when an OCR engine is installed. "
        "Results are persisted and can then be read via GET /{document_id}/text."
    ),
)
def extract_text(
    document_id: str,
    db: DbSession,
    user: CurrentUser,
) -> ExtractionResponse:
    document = analysis_service.require_document(db, document_id, user)
    extraction = text_extraction.extract_document_text(db, document)
    return _extraction_response(document, extraction)


@router.get(
    "/{document_id}/text",
    response_model=ExtractionResponse,
    summary="Retrieve extracted text",
    description=(
        "Return the stored extraction result including page-wise text, statistics "
        "and the extraction method used. Returns 404 when extraction has not run yet."
    ),
)
def get_text(
    document_id: str,
    db: DbSession,
    user: CurrentUser,
) -> ExtractionResponse:
    document = analysis_service.require_document(db, document_id, user)
    extraction = text_extraction.require_extraction(db, document)
    return _extraction_response(document, extraction)
