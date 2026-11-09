"""Document upload, listing, detail and deletion tests."""

from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from tests.conftest import JPEG_BYTES, PNG_BYTES, make_pdf_bytes


def _stored_files(upload_dir: Path) -> list[Path]:
    return sorted(p for p in upload_dir.iterdir() if p.is_file())


# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------


def test_successful_pdf_upload(client: TestClient, upload_file, upload_dir: Path) -> None:
    pdf_bytes = make_pdf_bytes()
    response = upload_file("report.pdf", pdf_bytes)

    assert response.status_code == 201
    data = response.json()
    UUID(data["id"])  # valid UUID
    assert data["original_filename"] == "report.pdf"
    assert data["file_extension"] == "pdf"
    assert data["mime_type"] == "application/pdf"
    assert data["file_size"] == len(pdf_bytes)
    assert len(data["sha256_hash"]) == 64
    assert data["processing_status"] == "completed"
    assert data["page_count"] == 1
    assert data["pdf_metadata"]["page_count"] == 1
    assert "metadata" in data["pdf_metadata"]
    assert "stored_filename" not in data
    assert str(upload_dir) not in response.text

    files = _stored_files(upload_dir)
    assert len(files) == 1
    assert files[0].suffix == ".pdf"


def test_successful_png_upload(client: TestClient, upload_file, upload_dir: Path) -> None:
    response = upload_file("image.png", PNG_BYTES)

    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == "image.png"
    assert data["file_extension"] == "png"
    assert data["mime_type"] == "image/png"
    assert data["file_size"] == len(PNG_BYTES)
    assert data["page_count"] is None
    assert data["pdf_metadata"] is None
    assert _stored_files(upload_dir)[0].suffix == ".png"


def test_successful_jpeg_upload(client: TestClient, upload_file, upload_dir: Path) -> None:
    response = upload_file("photo.jpeg", JPEG_BYTES)

    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == "photo.jpeg"
    assert data["file_extension"] == "jpeg"
    assert data["mime_type"] == "image/jpeg"
    assert data["file_size"] == len(JPEG_BYTES)
    assert _stored_files(upload_dir)[0].suffix == ".jpeg"


def test_jpg_extension_upload(upload_file) -> None:
    response = upload_file("photo.jpg", JPEG_BYTES)
    assert response.status_code == 201
    assert response.json()["file_extension"] == "jpg"


def test_unsupported_file_type_rejected(client: TestClient, upload_file, upload_dir: Path) -> None:
    response = upload_file("notes.txt", b"plain text content")

    assert response.status_code == 415
    assert "detail" in response.json()
    assert client.get("/api/v1/documents").json()["total"] == 0
    assert _stored_files(upload_dir) == []


def test_invalid_file_signature_rejected(client: TestClient, upload_file, upload_dir: Path) -> None:
    response = upload_file("fake.pdf", PNG_BYTES)

    assert response.status_code == 400
    assert "content does not match" in response.json()["detail"].lower()
    assert client.get("/api/v1/documents").json()["total"] == 0
    assert _stored_files(upload_dir) == []


def test_oversized_upload_rejected(client: TestClient, upload_file, upload_dir: Path) -> None:
    oversized = PNG_BYTES + b"\x00" * (2 * 1024 * 1024)
    response = upload_file("huge.png", oversized)

    assert response.status_code == 413
    assert "detail" in response.json()
    assert client.get("/api/v1/documents").json()["total"] == 0
    assert _stored_files(upload_dir) == []


def test_empty_upload_rejected(client: TestClient, upload_file, upload_dir: Path) -> None:
    response = upload_file("empty.pdf", b"")

    assert response.status_code == 400
    assert "detail" in response.json()
    assert client.get("/api/v1/documents").json()["total"] == 0
    assert _stored_files(upload_dir) == []


def test_missing_file_field_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/documents/upload")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def test_document_listing(client: TestClient, upload_file) -> None:
    upload_file("alpha.pdf", make_pdf_bytes("alpha"))
    upload_file("beta.pdf", make_pdf_bytes("beta"))
    upload_file("gamma.png", PNG_BYTES)

    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["items"][0]["original_filename"] == "gamma.png"
    assert "stored_filename" not in data["items"][0]


def test_document_listing_pagination(client: TestClient, upload_file) -> None:
    for index in range(3):
        upload_file(f"doc{index}.pdf", make_pdf_bytes(str(index)))

    page_one = client.get("/api/v1/documents?page=1&page_size=2").json()
    page_two = client.get("/api/v1/documents?page=2&page_size=2").json()

    assert page_one["total"] == 3
    assert len(page_one["items"]) == 2
    assert page_two["total"] == 3
    assert len(page_two["items"]) == 1
    assert page_one["items"][0]["original_filename"] == "doc2.pdf"
    assert page_two["items"][0]["original_filename"] == "doc0.pdf"


def test_document_listing_search(client: TestClient, upload_file) -> None:
    upload_file("invoice-march.pdf", make_pdf_bytes("invoice"))
    upload_file("contract.pdf", make_pdf_bytes("contract"))
    upload_file("photo.JPG", JPEG_BYTES)

    response = client.get("/api/v1/documents", params={"search": "invoice"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["original_filename"] == "invoice-march.pdf"

    upper = client.get("/api/v1/documents", params={"search": "PHOTO"}).json()
    assert upper["total"] == 1
    assert upper["items"][0]["original_filename"] == "photo.JPG"

    none = client.get("/api/v1/documents", params={"search": "zzz"}).json()
    assert none["total"] == 0
    assert none["items"] == []


def test_document_listing_invalid_pagination(client: TestClient) -> None:
    assert client.get("/api/v1/documents", params={"page": 0}).status_code == 422
    assert client.get("/api/v1/documents", params={"page_size": 1000}).status_code == 422


# ---------------------------------------------------------------------------
# Details
# ---------------------------------------------------------------------------


def test_document_detail(client: TestClient, upload_file) -> None:
    upload_response = upload_file("detail.pdf", make_pdf_bytes())
    document_id = upload_response.json()["id"]

    response = client.get(f"/api/v1/documents/{document_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == document_id
    assert data["original_filename"] == "detail.pdf"
    assert data["page_count"] == 1
    assert len(data["sha256_hash"]) == 64
    assert "stored_filename" not in data


def test_nonexistent_document_detail(client: TestClient) -> None:
    response = client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found."


def test_invalid_document_id_detail(client: TestClient) -> None:
    response = client.get("/api/v1/documents/not-a-valid-id")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------


def test_document_deletion(client: TestClient, upload_file, upload_dir: Path) -> None:
    upload_response = upload_file("delete-me.pdf", make_pdf_bytes())
    document_id = upload_response.json()["id"]
    assert len(_stored_files(upload_dir)) == 1

    response = client.delete(f"/api/v1/documents/{document_id}")
    assert response.status_code == 200
    assert "message" in response.json()

    assert client.get(f"/api/v1/documents/{document_id}").status_code == 404
    assert client.get("/api/v1/documents").json()["total"] == 0
    assert _stored_files(upload_dir) == []


def test_delete_nonexistent_document(client: TestClient) -> None:
    response = client.delete("/api/v1/documents/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_delete_document_with_missing_file_is_graceful(
    client: TestClient, upload_file, upload_dir: Path
) -> None:
    upload_response = upload_file("ghost.pdf", make_pdf_bytes())
    document_id = upload_response.json()["id"]
    for path in _stored_files(upload_dir):
        path.unlink()

    response = client.delete(f"/api/v1/documents/{document_id}")
    assert response.status_code == 200
    assert client.get("/api/v1/documents").json()["total"] == 0
