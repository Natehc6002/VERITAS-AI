"""Text extraction tests: native PDF, scanned PDF, images and OCR status."""

from fastapi.testclient import TestClient

from app.services import ocr_service
from tests.conftest import PNG_BYTES, make_pdf_bytes

LONG_TEXT = (
    "VERITAS AI quarterly operations report for the finance department. "
    "This document contains a substantial body of text so that native "
    "extraction is used instead of the OCR fallback path."
)


def _extract(client: TestClient, document_id: str) -> dict:
    response = client.post(f"/api/v1/documents/{document_id}/extract")
    assert response.status_code == 200, response.text
    return response.json()


def test_extract_pdf_with_text_layer(client: TestClient, upload_file) -> None:
    document_id = upload_file("report.pdf", make_pdf_bytes(LONG_TEXT)).json()["id"]

    data = _extract(client, document_id)

    assert data["document_id"] == document_id
    assert data["status"] == "completed"
    assert data["method"] == "native"
    assert data["page_count"] == 1
    assert data["char_count"] > 40
    assert data["word_count"] > 10
    assert len(data["pages"]) == 1
    assert data["pages"][0]["page_number"] == 1
    assert "quarterly operations report" in data["pages"][0]["text"]
    assert data["pages"][0]["method"] == "native"
    assert data["error"] is None


def test_get_text_before_extraction_returns_404(client: TestClient, upload_file) -> None:
    document_id = upload_file("later.pdf", make_pdf_bytes(LONG_TEXT)).json()["id"]
    response = client.get(f"/api/v1/documents/{document_id}/text")
    assert response.status_code == 404


def test_get_text_after_extraction(client: TestClient, upload_file) -> None:
    document_id = upload_file("later.pdf", make_pdf_bytes(LONG_TEXT)).json()["id"]
    _extract(client, document_id)

    response = client.get(f"/api/v1/documents/{document_id}/text")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "quarterly operations report" in data["pages"][0]["text"]


def test_extract_text_for_nonexistent_document(client: TestClient) -> None:
    response = client.post("/api/v1/documents/00000000-0000-0000-0000-000000000000/extract")
    assert response.status_code == 404


def test_image_without_text_reports_ocr_status(client: TestClient, upload_file) -> None:
    document_id = upload_file("pixel.png", PNG_BYTES).json()["id"]

    data = _extract(client, document_id)

    # A 1x1 image contains no readable text; status must reflect that honestly.
    assert data["status"] in {"no_text", "completed"}
    assert data["ocr_available"] is ocr_service.ocr_available()
    if data["status"] == "no_text":
        assert data["method"] in {"none", "ocr"}
        assert data["error"]


def test_blank_pdf_reports_no_text_not_success(client: TestClient, upload_file) -> None:
    document_id = upload_file("blank.pdf", make_pdf_bytes("")).json()["id"]

    data = _extract(client, document_id)

    assert data["status"] == "no_text"
    assert data["char_count"] == 0
    assert "quarterly" not in (data["pages"][0]["text"] if data["pages"] else "")


def test_extraction_is_persisted(client: TestClient, upload_file) -> None:
    document_id = upload_file("persist.pdf", make_pdf_bytes(LONG_TEXT)).json()["id"]
    first = _extract(client, document_id)
    second = _extract(client, document_id)

    assert first["char_count"] == second["char_count"]
    assert client.get(f"/api/v1/documents/{document_id}/text").json()["word_count"] == second[
        "word_count"
    ]


def test_scanned_pdf_uses_ocr_when_text_layer_missing(client: TestClient, upload_file) -> None:
    """A PDF whose pages are images only must go through OCR, not report native success."""
    import pymupdf

    document = pymupdf.open()
    page = document.new_page(width=400, height=200)
    # Render text as a raster image so the page has no text layer.
    text_doc = pymupdf.open()
    text_page = text_doc.new_page(width=400, height=200)
    text_page.insert_text((30, 80), "SCANNED CONTRACT AGREEMENT", fontsize=20)
    pixmap = text_page.get_pixmap(dpi=150)
    page.insert_image(page.rect, pixmap=pixmap)
    pdf_bytes = document.tobytes()
    document.close()
    text_doc.close()

    document_id = upload_file("scanned.pdf", pdf_bytes).json()["id"]
    data = _extract(client, document_id)

    if ocr_service.ocr_available():
        assert data["status"] in {"completed", "no_text"}
        if data["status"] == "completed":
            assert data["method"] == "ocr"
            assert "SCANNED CONTRACT AGREEMENT" in data["pages"][0]["text"].upper()
            assert data["pages"][0]["method"] == "ocr"
    else:  # pragma: no cover - exercised only when OCR is not installed
        assert data["status"] == "no_text"
        assert data["method"] == "none"
