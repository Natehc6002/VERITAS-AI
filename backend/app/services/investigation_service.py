"""Investigation CRUD scoped to the owning user."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, InvestigationNotFoundError
from app.models.document import Document
from app.models.user import Investigation, User


def list_investigations(db: Session, user: User) -> list[Investigation]:
    return list(
        db.scalars(
            select(Investigation)
            .where(Investigation.owner_id == user.id)
            .order_by(Investigation.created_at.asc())
        ).all()
    )


def create_investigation(
    db: Session, user: User, name: str, description: str | None
) -> Investigation:
    investigation = Investigation(owner_id=user.id, name=name.strip(), description=description)
    db.add(investigation)
    db.commit()
    db.refresh(investigation)
    return investigation


def get_investigation(db: Session, user: User, investigation_id: str) -> Investigation:
    investigation = _fetch_owned(db, user, investigation_id)
    if investigation is None:
        raise InvestigationNotFoundError("Investigation not found.")
    return investigation


def update_investigation(
    db: Session, user: User, investigation_id: str, name: str | None, description: str | None
) -> Investigation:
    investigation = _fetch_owned(db, user, investigation_id)
    if investigation is None:
        raise InvestigationNotFoundError("Investigation not found.")
    if name is not None:
        investigation.name = name.strip()
    if description is not None:
        investigation.description = description
    db.commit()
    db.refresh(investigation)
    return investigation


def delete_investigation(db: Session, user: User, investigation_id: str) -> None:
    investigation = _fetch_owned(db, user, investigation_id)
    if investigation is None:
        raise InvestigationNotFoundError("Investigation not found.")
    db.execute(
        update(Document)
        .where(Document.investigation_id == investigation.id)
        .values(investigation_id=None)
    )
    db.delete(investigation)
    db.commit()


def _fetch_owned(db: Session, user: User, investigation_id: str) -> Investigation | None:
    from uuid import UUID

    try:
        UUID(str(investigation_id))
    except (ValueError, TypeError, AttributeError):
        return None
    investigation = db.get(Investigation, str(investigation_id))
    if investigation is None or investigation.owner_id != user.id:
        return None
    return investigation
