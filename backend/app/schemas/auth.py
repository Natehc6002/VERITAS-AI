"""Pydantic request/response models for authentication and investigations."""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("Enter a valid email address.")
    return normalized


class RegisterRequest(BaseModel):
    """New account credentials."""

    email: str = Field(min_length=3, max_length=255, description="Account email address.")
    password: str = Field(min_length=8, max_length=128, description="Password (min 8 chars).")

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return _normalize_email(value)


class LoginRequest(BaseModel):
    """Existing account credentials."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return _normalize_email(value)


class UserResponse(BaseModel):
    """Public account representation (never exposes the password hash)."""

    model_config = {"from_attributes": True}

    id: str
    email: str
    created_at: datetime


class InvestigationCreate(BaseModel):
    """Fields for creating an investigation."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class InvestigationUpdate(BaseModel):
    """Partial update for an investigation."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class InvestigationResponse(BaseModel):
    """Investigation representation."""

    model_config = {"from_attributes": True}

    id: str
    name: str
    description: str | None = None
    owner_id: str
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """Access token issued at registration or login."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    investigation: InvestigationResponse | None = None


class AuthContextResponse(BaseModel):
    """The authenticated user plus their investigations."""

    user: UserResponse
    investigations: list[InvestigationResponse]
