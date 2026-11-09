"""Environment-driven application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "VERITAS AI"
    debug: bool = False
    database_url: str = f"sqlite:///{BACKEND_ROOT / 'veritas.db'}"
    upload_dir: Path = BACKEND_ROOT / "uploads"
    max_upload_size_mb: int = 20
    allowed_origins: str = "http://localhost:5173"
    auth_secret_key: str = ""
    access_token_ttl_minutes: int = 720

    @field_validator("upload_dir", mode="before")
    @classmethod
    def _resolve_upload_dir(cls, value: object) -> object:
        if isinstance(value, str):
            path = Path(value)
            if not path.is_absolute():
                path = BACKEND_ROOT / path
            return path
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def _resolve_sqlite_url(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith("sqlite:///"):
            raw_path = value[len("sqlite:///") :]
            path = Path(raw_path)
            if not path.is_absolute():
                path = BACKEND_ROOT / path
            return f"sqlite:///{path.as_posix()}"
        return value

    @field_validator("max_upload_size_mb")
    @classmethod
    def _validate_upload_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MAX_UPLOAD_SIZE_MB must be a positive integer.")
        return value

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
