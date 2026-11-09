"""Shared test fixtures: isolated temp database, upload dir and sample files."""

import base64
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="veritas_test_"))

# Must be set before any application module is imported.
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_ROOT / 'test.db'}"
os.environ["UPLOAD_DIR"] = str(_TEST_ROOT / "uploads")
os.environ["MAX_UPLOAD_SIZE_MB"] = "1"
os.environ["DEBUG"] = "true"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:5173"
os.environ["AUTH_SECRET_KEY"] = "test-signing-key-not-for-production"

import pymupdf  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
from app.main import create_app  # noqa: E402

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
JPEG_BYTES = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIy"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIA"
    "AhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA"
    "AAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3"
    "ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm"
    "p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEA"
    "AwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExB"
    "hJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1"
    "RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm"
    "6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq+vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigD//2Q=="
)


def make_pdf_bytes(text: str = "VERITAS AI test document") -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


@pytest.fixture()
def client() -> TestClient:
    """App client bound to a fresh temp database, registered and authenticated."""
    settings = get_settings()
    Base.metadata.drop_all(bind=engine)
    if settings.upload_dir.exists():
        shutil.rmtree(settings.upload_dir, ignore_errors=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    with TestClient(create_app()) as test_client:
        register = test_client.post(
            "/api/v1/auth/register",
            json={"email": "tester@veritas.test", "password": "test-password-123"},
        )
        assert register.status_code == 201, register.text
        token = register.json()["access_token"]
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        yield test_client


def register_user(client: TestClient, email: str, password: str = "test-password-123") -> str:
    """Register an account and return its bearer token (does not change client headers)."""
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def upload_dir() -> Path:
    return get_settings().upload_dir


@pytest.fixture()
def upload_file(client: TestClient) -> Callable[..., object]:
    """POST helper that always sends an untrusted client MIME type."""

    def _upload(
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ):
        return client.post(
            "/api/v1/documents/upload",
            files={"file": (filename, content, content_type)},
        )

    return _upload
