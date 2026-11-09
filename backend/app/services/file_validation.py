"""File type validation and secure streaming of uploads to disk."""

import hashlib
from pathlib import Path

from fastapi import UploadFile

from app.core.errors import (
    EmptyUploadError,
    FileTooLargeError,
    InvalidFileSignatureError,
    UnsupportedFileTypeError,
)

CHUNK_SIZE = 1024 * 1024

ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

_PDF_MAGIC = b"%PDF-"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"


def validate_extension(filename: str | None) -> str:
    """Return the normalised extension or raise 415 for unsupported types."""
    if not filename or not filename.strip():
        raise UnsupportedFileTypeError("A filename is required for the upload.")
    suffix = Path(filename.replace("\\", "/")).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{suffix or filename}'. Allowed types: {allowed}."
        )
    return suffix


def detect_mime_type(head: bytes) -> str | None:
    """Identify the real content type from magic bytes (never trust client MIME)."""
    if head.startswith(_PDF_MAGIC):
        return "application/pdf"
    if head.startswith(_PNG_MAGIC):
        return "image/png"
    if head.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    return None


def save_upload(
    upload: UploadFile,
    destination: Path,
    max_bytes: int,
    expected_mime: str,
) -> tuple[int, str]:
    """Stream an upload to ``destination`` while enforcing size and signature checks.

    Returns ``(file_size, sha256_hexdigest)``. The destination file is removed if
    any validation or write error occurs.
    """
    digest = hashlib.sha256()
    size = 0
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        with destination.open("wb") as output:
            while True:
                chunk = upload.file.read(CHUNK_SIZE)
                if not chunk:
                    break
                if size == 0:
                    detected = detect_mime_type(chunk)
                    if detected is None:
                        raise InvalidFileSignatureError(
                            "File content does not match a supported format signature."
                        )
                    if detected != expected_mime:
                        raise InvalidFileSignatureError(
                            "File content does not match the declared file extension."
                        )
                size += len(chunk)
                if size > max_bytes:
                    limit_mb = max_bytes // (1024 * 1024)
                    raise FileTooLargeError(
                        f"File exceeds the maximum allowed size of {limit_mb} MB."
                    )
                digest.update(chunk)
                output.write(chunk)
        if size == 0:
            raise EmptyUploadError("The uploaded file is empty.")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise

    return size, digest.hexdigest()
