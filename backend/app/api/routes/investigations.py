"""Investigation management endpoints (owner-scoped)."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import InvestigationCreate, InvestigationResponse, InvestigationUpdate
from app.schemas.document import MessageResponse
from app.services import investigation_service

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


@router.get(
    "",
    response_model=list[InvestigationResponse],
    summary="List investigations",
    description="Return every investigation owned by the authenticated user.",
)
def list_investigations(user: CurrentUser, db: DbSession) -> list[InvestigationResponse]:
    items = investigation_service.list_investigations(db, user)
    return [InvestigationResponse.model_validate(item) for item in items]


@router.post(
    "",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an investigation",
)
def create_investigation(
    payload: InvestigationCreate, user: CurrentUser, db: DbSession
) -> InvestigationResponse:
    item = investigation_service.create_investigation(
        db, user, payload.name, payload.description
    )
    return InvestigationResponse.model_validate(item)


@router.get(
    "/{investigation_id}",
    response_model=InvestigationResponse,
    summary="Get an investigation",
    responses={404: {"description": "Investigation not found."}},
)
def get_investigation(
    investigation_id: str, user: CurrentUser, db: DbSession
) -> InvestigationResponse:
    item = investigation_service.get_investigation(db, user, investigation_id)
    return InvestigationResponse.model_validate(item)


@router.patch(
    "/{investigation_id}",
    response_model=InvestigationResponse,
    summary="Update an investigation",
    responses={404: {"description": "Investigation not found."}},
)
def update_investigation(
    investigation_id: str,
    payload: InvestigationUpdate,
    user: CurrentUser,
    db: DbSession,
) -> InvestigationResponse:
    item = investigation_service.update_investigation(
        db, user, investigation_id, payload.name, payload.description
    )
    return InvestigationResponse.model_validate(item)


@router.delete(
    "/{investigation_id}",
    response_model=MessageResponse,
    summary="Delete an investigation",
    description=(
        "Delete the investigation. Documents inside it remain owned by the user "
        "but are moved out of the investigation."
    ),
    responses={404: {"description": "Investigation not found."}},
)
def delete_investigation(
    investigation_id: str, user: CurrentUser, db: DbSession
) -> MessageResponse:
    investigation_service.delete_investigation(db, user, investigation_id)
    return MessageResponse(message="Investigation deleted successfully.")
