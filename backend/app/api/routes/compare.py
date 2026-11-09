"""Cross-document comparison endpoint."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.intelligence import CompareRequest, CompareResponse
from app.services import analysis_service, cross_document

router = APIRouter(prefix="/api/v1", tags=["comparison"])


@router.post(
    "/compare",
    response_model=CompareResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare multiple documents",
    description=(
        "Run an explainable cross-document comparison over two or more documents. "
        "Documents that have not been analysed yet are analysed automatically. "
        "Returns shared entities, related record pairs and detected conflicts."
    ),
)
def compare_documents(
    payload: CompareRequest,
    db: Session = Depends(get_db),
) -> CompareResponse:
    for document_id in payload.document_ids:
        document = analysis_service.require_document(db, document_id)
        analysis_service.get_or_run_analysis(db, document)

    report = cross_document.compare_documents(db, payload.document_ids)
    return CompareResponse(**report)
