"""Document understanding, forensic findings, evidence and statistics."""

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.intelligence import Evidence, Finding
from app.schemas.intelligence import (
    AnalysisResponse,
    EntityResponse,
    EvidenceResponse,
    FindingResponse,
    StatsResponse,
)
from app.services import analysis_service

router = APIRouter(prefix="/api/v1", tags=["analysis"])


def _finding_response(finding: Finding, evidence: list[Evidence]) -> FindingResponse:
    return FindingResponse(
        id=finding.id,
        category=finding.category,
        severity=finding.severity,
        confidence=finding.confidence,
        title=finding.title,
        explanation=finding.explanation,
        detection_method=finding.detection_method,
        page_number=finding.page_number,
        created_at=finding.created_at,
        evidence=[
            EvidenceResponse(
                id=item.id,
                page_number=item.page_number,
                evidence_type=item.evidence_type,
                source_ref=item.source_ref,
                excerpt=item.excerpt,
                explanation=item.explanation,
            )
            for item in evidence
            if item.finding_id == finding.id
        ],
    )


@router.post(
    "/documents/{document_id}/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Run full document analysis",
    description=(
        "Run extraction (if needed), rule-based classification, entity extraction "
        "and forensic indicator detection, then persist all results. Returns the "
        "complete analysis bundle including evidence references."
    ),
)
def analyze_document(
    document_id: str,
    db: DbSession,
    user: CurrentUser,
) -> AnalysisResponse:
    document = analysis_service.require_document(db, document_id, user)
    bundle = analysis_service.run_analysis(db, document)
    return AnalysisResponse(**bundle)


@router.get(
    "/documents/{document_id}/analysis",
    response_model=AnalysisResponse,
    summary="Retrieve document analysis",
    description=(
        "Return the stored analysis bundle (extraction, classification, summary, "
        "entities, findings and evidence). If analysis has not run yet it is "
        "executed on demand."
    ),
)
def get_analysis(
    document_id: str,
    db: DbSession,
    user: CurrentUser,
) -> AnalysisResponse:
    document = analysis_service.require_document(db, document_id, user)
    bundle = analysis_service.get_or_run_analysis(db, document)
    return AnalysisResponse(**bundle)


@router.get(
    "/documents/{document_id}/findings",
    response_model=list[FindingResponse],
    summary="List forensic findings for a document",
    description="Return explainable forensic indicators with their supporting evidence.",
)
def list_findings(
    document_id: str,
    db: DbSession,
    user: CurrentUser,
) -> list[FindingResponse]:
    document = analysis_service.require_document(db, document_id, user)
    findings = list(
        db.scalars(select(Finding).where(Finding.document_id == document.id)).all()
    )
    evidence = list(
        db.scalars(select(Evidence).where(Evidence.document_id == document.id)).all()
    )
    return [_finding_response(finding, evidence) for finding in findings]


@router.get(
    "/documents/{document_id}/entities",
    response_model=list[EntityResponse],
    summary="List extracted entities for a document",
)
def list_entities(
    document_id: str,
    db: DbSession,
    user: CurrentUser,
) -> list[EntityResponse]:
    from app.models.intelligence import Entity  # noqa: PLC0415

    document = analysis_service.require_document(db, document_id, user)
    entities = list(db.scalars(select(Entity).where(Entity.document_id == document.id)).all())
    return [
        EntityResponse(
            id=entity.id,
            entity_type=entity.entity_type,
            value=entity.value,
            normalized_value=entity.normalized_value,
            confidence=entity.confidence,
            page_number=entity.page_number,
            source_text=entity.source_text,
        )
        for entity in entities
    ]


@router.get(
    "/documents/{document_id}/evidence",
    response_model=list[EvidenceResponse],
    summary="List evidence rows for a document",
    description=(
        "Return every evidence row recorded for the document, including evidence "
        "attached to findings and document-level observations."
    ),
)
def list_evidence(
    document_id: str,
    db: DbSession,
    user: CurrentUser,
) -> list[EvidenceResponse]:
    document = analysis_service.require_document(db, document_id, user)
    rows = list(db.scalars(select(Evidence).where(Evidence.document_id == document.id)).all())
    return [
        EvidenceResponse(
            id=row.id,
            page_number=row.page_number,
            evidence_type=row.evidence_type,
            source_ref=row.source_ref,
            excerpt=row.excerpt,
            explanation=row.explanation,
        )
        for row in rows
    ]


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Dashboard statistics",
    description="Aggregate counters derived from real database rows, scoped to the user.",
)
def get_stats(db: DbSession, user: CurrentUser) -> StatsResponse:
    return StatsResponse(**analysis_service.document_stats(db, user))
