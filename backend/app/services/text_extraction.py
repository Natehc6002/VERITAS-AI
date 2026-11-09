"""Text extraction for PDFs (native) and images/scanned pages (OCR)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pymupdf
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DocumentNotFoundError, VeritasError
from app.models.document import Document
from app.models.intelligence import (
    ExtractionMethod,
    ExtractionStatus,
    TextExtraction,
)
from app.services import ocr_service

logger = logging.getLogger(__name__)

# A page needs at least this many non-whitespace characters to count as
# "meaningfully extractable" without OCR.
MIN_PAGE_CHARS = 20
MIN_TOTAL_CHARS = 40


class ExtractionNotPossibleError(VeritasError):
    status_code = 409


def _stored_path(document: Document) -> Path:
    return get_settings().upload_dir / document.stored_filename


def _word_count(text: str) -> int:
    return len(text.split())


def _page_entry(page_number: int, text: str, method: str, confidence: float | None) -> dict[str, Any]:
    return {
        "page_number": page_number,
        "text": text,
        "char_count": len(text),
        "word_count": _word_count(text),
        "method": method,
        "confidence": confidence,
    }


def extract_document_text(db: Session, document: Document) -> TextExtraction:
    """Run (or re-run) text extraction for a document and persist the result."""
    path = _stored_path(document)
    if not path.exists():
        raise ExtractionNotPossibleError(
            "The stored file for this document is missing, so text cannot be extracted."
        )

    existing = (
        db.query(TextExtraction).filter(TextExtraction.document_id == document.id).first()
    )

    try:
        if document.file_extension == "pdf":
            result = _extract_pdf(path)
        else:
            result = _extract_image(path)
    except ExtractionNotPossibleError as exc:
        result = {
            "status": ExtractionStatus.FAILED.value,
            "method": ExtractionMethod.NONE.value,
            "pages": [],
            "full_text": None,
            "error": exc.message,
        }
    except Exception as exc:  # noqa: BLE001 - never let extraction crash the API
        logger.exception("Text extraction failed for document %s", document.id)
        result = {
            "status": ExtractionStatus.FAILED.value,
            "method": ExtractionMethod.NONE.value,
            "pages": [],
            "full_text": None,
            "error": f"Text extraction failed: {type(exc).__name__}: {exc}",
        }

    pages: list[dict[str, Any]] = result["pages"]
    full_text = result.get("full_text")
    if full_text is None:
        full_text = "\n\n".join(page["text"] for page in pages if page["text"])

    if existing is None:
        existing = TextExtraction(document_id=document.id)
        db.add(existing)

    existing.status = result["status"]
    existing.method = result["method"]
    existing.full_text = full_text or None
    existing.pages = pages
    existing.page_count = result.get("page_count")
    existing.char_count = sum(page["char_count"] for page in pages)
    existing.word_count = sum(page["word_count"] for page in pages)
    existing.ocr_available = ocr_service.ocr_available()
    existing.error = result.get("error")
    db.commit()
    db.refresh(existing)
    return existing


def get_extraction(db: Session, document: Document) -> TextExtraction | None:
    return (
        db.query(TextExtraction).filter(TextExtraction.document_id == document.id).first()
    )


def _extract_pdf(path: Path) -> dict[str, Any]:
    """Native PyMuPDF extraction with scanned-document detection."""
    try:
        pdf = pymupdf.open(path)
    except Exception as exc:
        raise ExtractionNotPossibleError("The PDF file is corrupt or unreadable.") from exc

    try:
        if pdf.needs_pass:
            raise ExtractionNotPossibleError("The PDF file is password protected.")
        pages: list[dict[str, Any]] = []
        for index in range(pdf.page_count):
            text = pdf.load_page(index).get_text("text") or ""
            pages.append(_page_entry(index + 1, text, ExtractionMethod.NATIVE.value, None))
    finally:
        pdf.close()

    total_chars = sum(page["char_count"] for page in pages)
    if total_chars < MIN_TOTAL_CHARS:
        # Scanned / image-only PDF: native extraction found no usable text layer.
        ocr_pages, error = _ocr_pdf_pages(path, pages)
        if ocr_pages is not None:
            return {
                "status": _status_for(ocr_pages),
                "method": ExtractionMethod.OCR.value,
                "pages": ocr_pages,
                "full_text": None,
                "page_count": len(ocr_pages),
                "error": error,
            }
        return {
            "status": ExtractionStatus.NO_TEXT.value,
            "method": ExtractionMethod.NONE.value,
            "pages": pages,
            "full_text": "",
            "page_count": len(pages),
            "error": error,
        }

    return {
        "status": ExtractionStatus.COMPLETED.value,
        "method": ExtractionMethod.NATIVE.value,
        "pages": pages,
        "full_text": None,
        "page_count": len(pages),
        "error": None,
    }


def _ocr_pdf_pages(path: Path, pages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Attempt OCR for a text-scarce PDF. Returns (pages, error_or_None)."""
    if not ocr_service.ocr_available():
        return None, (
            "No meaningful text layer was found (likely a scanned PDF) and no OCR "
            "engine is installed. " + ocr_service.ocr_unavailable_reason()
        )

    try:
        pdf = pymupdf.open(path)
    except Exception as exc:
        return None, f"Could not open PDF for OCR: {exc}"

    ocr_pages: list[dict[str, Any]] = []
    try:
        for index in range(pdf.page_count):
            page = pdf.load_page(index)
            native = pages[index]["text"] if index < len(pages) else ""
            if len(native.strip()) >= MIN_PAGE_CHARS:
                ocr_pages.append(_page_entry(index + 1, native, ExtractionMethod.NATIVE.value, None))
                continue
            pixmap = page.get_pixmap(dpi=200)
            image_path = path.parent / f"{path.stem}_p{index + 1}.png"
            try:
                pixmap.save(image_path)
                result = ocr_service.recognize_file(image_path)
                ocr_pages.append(
                    _page_entry(index + 1, result.text, ExtractionMethod.OCR.value, result.confidence)
                )
            except Exception as exc:  # noqa: BLE001 - OCR failure must not abort the run
                logger.warning("OCR failed for page %s of %s: %s", index + 1, path.name, exc)
                ocr_pages.append(_page_entry(index + 1, native, ExtractionMethod.NATIVE.value, None))
            finally:
                image_path.unlink(missing_ok=True)
    finally:
        pdf.close()

    return ocr_pages, None


def _extract_image(path: Path) -> dict[str, Any]:
    """Images have no native text layer; OCR is the only source of text."""
    if not ocr_service.ocr_available():
        return {
            "status": ExtractionStatus.NO_TEXT.value,
            "method": ExtractionMethod.NONE.value,
            "pages": [_page_entry(1, "", ExtractionMethod.NONE.value, None)],
            "full_text": "",
            "page_count": 1,
            "error": (
                "Images contain no native text layer and no OCR engine is installed. "
                + ocr_service.ocr_unavailable_reason()
            ),
        }
    try:
        result = ocr_service.recognize_file(path)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": ExtractionStatus.FAILED.value,
            "method": ExtractionMethod.NONE.value,
            "pages": [],
            "full_text": None,
            "page_count": 1,
            "error": f"OCR failed: {type(exc).__name__}: {exc}",
        }

    page = _page_entry(1, result.text, ExtractionMethod.OCR.value, result.confidence)
    status = ExtractionStatus.COMPLETED.value if page["char_count"] >= MIN_PAGE_CHARS else ExtractionStatus.NO_TEXT.value
    error = None if status == ExtractionStatus.COMPLETED.value else "OCR completed but recognised no text."
    return {
        "status": status,
        "method": ExtractionMethod.OCR.value,
        "pages": [page],
        "full_text": None,
        "page_count": 1,
        "error": error,
    }


def _status_for(pages: list[dict[str, Any]]) -> str:
    total = sum(page["char_count"] for page in pages)
    return (
        ExtractionStatus.COMPLETED.value
        if total >= MIN_TOTAL_CHARS
        else ExtractionStatus.NO_TEXT.value
    )


def require_extraction(db: Session, document: Document) -> TextExtraction:
    extraction = get_extraction(db, document)
    if extraction is None:
        raise DocumentNotFoundError("No extraction result exists for this document yet.")
    return extraction
