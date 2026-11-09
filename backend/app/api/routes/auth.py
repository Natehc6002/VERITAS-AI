"""Authentication endpoints: register, login and current context."""

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import (
    AuthContextResponse,
    InvestigationResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth_service, investigation_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
    description=(
        "Register a new investigator account. The first account also claims any "
        "documents uploaded before authentication was enabled. Returns an access "
        "token together with the automatically created default investigation."
    ),
)
def register(payload: RegisterRequest, db: DbSession) -> TokenResponse:
    user, investigation, token = auth_service.register_user(db, payload.email, payload.password)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        investigation=InvestigationResponse.model_validate(investigation),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Sign in",
    description="Exchange email and password for a bearer access token.",
)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    user, investigation, token = auth_service.login_user(db, payload.email, payload.password)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
        investigation=(
            InvestigationResponse.model_validate(investigation) if investigation else None
        ),
    )


@router.get(
    "/me",
    response_model=AuthContextResponse,
    summary="Current user context",
    description="Return the authenticated user and all of their investigations.",
)
def me(user: CurrentUser, db: DbSession) -> AuthContextResponse:
    investigations = investigation_service.list_investigations(db, user)
    return AuthContextResponse(
        user=UserResponse.model_validate(user),
        investigations=[InvestigationResponse.model_validate(item) for item in investigations],
    )
