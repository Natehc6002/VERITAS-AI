"""Registration, login and token issuance."""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import resolve_token_secret
from app.core.config import get_settings
from app.core.errors import AuthenticationError, ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.document import Document
from app.models.user import Investigation, User, default_investigation_payload

logger = logging.getLogger(__name__)

_DUMMY_HASH_CACHE: list[str] = []


def register_user(db: Session, email: str, password: str) -> tuple[User, Investigation, str]:
    """Create an account, its default investigation and an access token."""
    normalized = email.strip().lower()
    existing = db.scalar(select(User).where(User.email == normalized))
    if existing is not None:
        raise ConflictError("An account with this email already exists.")

    first_user = (db.scalar(select(func.count()).select_from(User)) or 0) == 0

    user = User(email=normalized, password_hash=hash_password(password))
    db.add(user)
    db.flush()

    investigation = Investigation(owner_id=user.id, **default_investigation_payload())
    db.add(investigation)
    db.flush()

    if first_user:
        claimed = db.execute(
            update(Document)
            .where(Document.owner_id.is_(None))
            .values(owner_id=user.id, investigation_id=investigation.id)
        ).rowcount
        if claimed:
            logger.info("Claimed %s pre-auth document(s) for the first user.", claimed)

    db.commit()
    db.refresh(user)
    db.refresh(investigation)
    return user, investigation, _issue_token(user)


def login_user(db: Session, email: str, password: str) -> tuple[User, Investigation | None, str]:
    """Verify credentials and issue an access token."""
    normalized = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized))
    if user is None:
        verify_password(password, _dummy_hash())
        raise AuthenticationError("Invalid email or password.")
    if not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid email or password.")

    investigation = db.scalar(
        select(Investigation)
        .where(Investigation.owner_id == user.id)
        .order_by(Investigation.created_at.asc())
    )
    return user, investigation, _issue_token(user)


def _issue_token(user: User) -> str:
    settings = get_settings()
    ttl = int(timedelta(minutes=settings.access_token_ttl_minutes).total_seconds())
    return create_access_token(user.id, resolve_token_secret(), ttl_seconds=ttl)


def _dummy_hash() -> str:
    """A real hash of a random password so unknown-email logins cost the same."""
    if not _DUMMY_HASH_CACHE:
        _DUMMY_HASH_CACHE.append(hash_password("timing-equalizer-not-a-real-password"))
    return _DUMMY_HASH_CACHE[0]
