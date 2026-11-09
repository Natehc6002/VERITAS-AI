"""Shared FastAPI dependencies (authentication)."""

import logging
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AuthenticationError
from app.core.security import TokenError, generate_secret_key, parse_access_token
from app.models.user import User

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

INVALID_TOKEN_MESSAGE = "Invalid or expired access token."


def resolve_token_secret() -> str:
    """Return the configured signing key or a stable per-process ephemeral one."""
    configured = get_settings().auth_secret_key
    if configured:
        return configured
    return _ephemeral_secret()


def _ephemeral_secret() -> str:
    if not hasattr(_ephemeral_secret, "_cached"):
        _ephemeral_secret._cached = generate_secret_key()  # type: ignore[attr-defined]
        logger.warning(
            "AUTH_SECRET_KEY is not configured; using an ephemeral signing key. "
            "Access tokens will not survive a server restart."
        )
    return _ephemeral_secret._cached  # type: ignore[attr-defined]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve the bearer token to a persisted user or raise 401."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Authentication required. Provide a bearer token.")
    try:
        payload = parse_access_token(credentials.credentials, resolve_token_secret())
    except TokenError:
        raise AuthenticationError(INVALID_TOKEN_MESSAGE) from None
    user = db.get(User, payload["sub"])
    if user is None:
        raise AuthenticationError(INVALID_TOKEN_MESSAGE)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]
