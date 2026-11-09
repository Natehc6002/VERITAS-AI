"""Business logic for document upload, listing, retrieval and deletion."""

import logging
import uuid
from pathlib import Path
from typing import Any

import pymupdf
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    DocumentNotFoundError,
    InvestigationNotFoundError,
    PdfProcessingError,
    StorageError,
)
from app.models.document import Document, ProcessingStatus
from app.models.user import Investigation, User
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services import file_validation

logger = logging.getLogger(__name__)


def upload_document(
    db: Session,
    upload: UploadFile,
    user: User,
    investigation_id: str | None = None,
) -> Document:
    """Validate, store and register a newly uploaded document for ``user``."""
    if investigation_id is not None:
        _require_owned_investigation(db, user, investigation_id)

    settings = get_settings()
    extension = file_validation.validate_extension(upload.filename)
    expected_mime = file_validation.ALLOWED_EXTENSIONS[extension]

    stored_filename = f"{uuid.uuid4().hex}{extension}"
    destination = settings.upload_dir / stored_filename

    file_size, sha256_hash = file_validation.save_upload(
        upload=upload,
        destination=destination,
        max_bytes=settings.max_upload_size_bytes,
        expected_mime=expected_mime,
    )

    page_count: int | None = None
    pdf_metadata: dict[str, Any] | None = None
    if extension == ".pdf":
        try:
            page_count, pdf_metadata = _extract_pdf_metadata(destination)
        except PdfProcessingError:
            destination.unlink(missing_ok=True)
            raise

    document = Document(
        original_filename=Path(upload.filename.replace("\\", "/")).name,
        stored_filename=stored_filename,
        file_extension=extension.lstrip("."),
        mime_type=expected_mime,
        file_size=file_size,
        sha256_hash=sha256_hash,
        processing_status=ProcessingStatus.COMPLETED.value,
        page_count=page_count,
        pdf_metadata=pdf_metadata,
        owner_id=user.id,
        investigation_id=investigation_id,
    )

    try:
        db.add(document)
        db.commit()
        db.refresh(document)
    except SQLAlchemyError as exc:
        db.rollback()
        destination.unlink(missing_ok=True)
        logger.exception("Failed to persist document metadata for %s", stored_filename)
        raise StorageError("Failed to save document metadata.") from exc

    return document


def list_documents(
    db: Session,
    user: User,
    page: int,
    page_size: int,
    search: str | None,
    investigation_id: str | None = None,
) -> DocumentListResponse:
    """Return a paginated, newest-first listing scoped to ``user``."""
    stmt = select(Document).where(Document.owner_id == user.id)
    if investigation_id is not None:
        stmt = stmt.where(Document.investigation_id == investigation_id)
    if search and search.strip():
        pattern = f"%{_escape_like(search.strip())}%"
        stmt = stmt.where(Document.original_filename.ilike(pattern, escape="\\"))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = (
        stmt.order_by(Document.upload_timestamp.desc(), Document.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    documents = list(db.scalars(stmt).all())

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


def get_document(db: Session, document_id: str, user: User) -> Document:
    """Return a single owned document or raise 404 (also for foreign documents)."""
    document = _fetch_document(db, document_id, user)
    if document is None:
        raise DocumentNotFoundError("Document not found.")
    return document


def delete_document(db: Session, document_id: str, user: User) -> None:
    """Remove an owned document's database record, intelligence rows and stored file."""
    document = _fetch_document(db, document_id, user)
    if document is None:
        raise DocumentNotFoundError("Document not found.")

    stored_filename = document.stored_filename
    try:
        from app.services.analysis_service import delete_analysis_rows  # noqa: PLC0415

        delete_analysis_rows(db, document.id)
        db.delete(document)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Failed to delete document record %s", document_id)
        raise StorageError("Failed to delete document record.") from exc

    _remove_stored_file(stored_filename)


def _fetch_document(db: Session, document_id: str, user: User) -> Document | None:
    try:
        uuid.UUID(str(document_id))
    except (ValueError, TypeError, AttributeError):
        return None
    document = db.get(Document, str(document_id))
    if document is None or document.owner_id != user.id:
        return None
    return document


def _require_owned_investigation(db: Session, user: User, investigation_id: str) -> None:
    from uuid import UUID

    try:
        UUID(str(investigation_id))
    except (ValueError, TypeError, AttributeError):
        raise InvestigationNotFoundError("Investigation not found.") from None
    investigation = db.get(Investigation, str(investigation_id))
    if investigation is None or investigation.owner_id != user.id:
        raise InvestigationNotFoundError("Investigation not found.")


def _remove_stored_file(stored_filename: str) -> None:
    if Path(stored_filename).name != stored_filename:
        logger.warning("Refusing to delete suspicious stored filename %r", stored_filename)
        return
    path = get_settings().upload_dir / stored_filename
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Could not delete stored file %s: %s", stored_filename, exc)


def _extract_pdf_metadata(path: Path) -> tuple[int, dict[str, Any]]:
    """Read page count and basic metadata from a PDF; raise 400 on corrupt/locked files."""
    try:
        document = pymupdf.open(path)
    except Exception as exc:
        logger.warning("Unable to open PDF %s: %s", path.name, exc)
        raise PdfProcessingError("The PDF file is corrupt or unreadable.") from exc

    try:
        if document.needs_pass:
            raise PdfProcessingError("The PDF file is password protected.")
        try:
            page_count = document.page_count
            raw_metadata = dict(document.metadata or {})
        except Exception as exc:
            logger.warning("Unable to read PDF metadata from %s: %s", path.name, exc)
            raise PdfProcessingError("The PDF file is corrupt or unreadable.") from exc
    finally:
        document.close()

    metadata = {
        key: value
        for key, value in raw_metadata.items()
        if isinstance(value, str) and value.strip()
    }
    return page_count, {"page_count": page_count, "metadata": metadata}


def _escape_like(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
