"""Domain-level exceptions mapped to structured HTTP error responses."""


class VeritasError(Exception):
    """Base class for expected application errors."""

    status_code: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsupportedFileTypeError(VeritasError):
    status_code = 415


class InvalidFileSignatureError(VeritasError):
    status_code = 400


class EmptyUploadError(VeritasError):
    status_code = 400


class FileTooLargeError(VeritasError):
    status_code = 413


class PdfProcessingError(VeritasError):
    status_code = 400


class DocumentNotFoundError(VeritasError):
    status_code = 404


class StorageError(VeritasError):
    status_code = 500
