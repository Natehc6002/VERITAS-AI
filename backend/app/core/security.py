"""Password hashing and stateless access-token signing (stdlib only).

Password format: ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``

Tokens: ``v1.<base64url(payload_json)>.<base64url(hmac_sha256_signature)>``

Both use the standard library (hashlib/hmac/secrets) so no extra dependency is
introduced. Tokens are signed, tamper-evident and carry an expiry.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

PBKDF2_ITERATIONS = 390_000
TOKEN_VERSION = "v1"
DEFAULT_TOKEN_TTL_SECONDS = 12 * 60 * 60


class TokenError(Exception):
    """Raised when an access token is missing, malformed, forged or expired."""


# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations_raw, salt_hex, hash_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------

def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_access_token(
    user_id: str,
    secret: str,
    ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
    extra: dict[str, Any] | None = None,
) -> str:
    if not secret:
        raise ValueError("An authentication secret is required to sign tokens.")
    payload: dict[str, Any] = {"sub": user_id, "exp": int(time.time()) + ttl_seconds, "v": 1}
    if extra:
        payload.update(extra)
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    body = f"{TOKEN_VERSION}.{_b64url_encode(payload_json)}"
    signature = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url_encode(signature)}"


def parse_access_token(token: str, secret: str) -> dict[str, Any]:
    """Verify signature and expiry; return the payload or raise TokenError."""
    if not secret:
        raise TokenError("Authentication is not configured.")
    try:
        version, body, signature = token.split(".")
    except ValueError:
        raise TokenError("Malformed access token.") from None
    if version != TOKEN_VERSION:
        raise TokenError("Unsupported token version.")

    signed = f"{TOKEN_VERSION}.{body}"
    expected = hmac.new(secret.encode("utf-8"), signed.encode("ascii"), hashlib.sha256).digest()
    try:
        provided = _b64url_decode(signature)
    except (ValueError, TypeError):
        raise TokenError("Malformed token signature.") from None
    if not hmac.compare_digest(expected, provided):
        raise TokenError("Invalid token signature.")

    try:
        payload = json.loads(_b64url_decode(body))
    except (ValueError, TypeError):
        raise TokenError("Malformed token payload.") from None
    if not isinstance(payload, dict):
        raise TokenError("Malformed token payload.")

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        raise TokenError("Access token has expired.")
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise TokenError("Token missing subject.")
    return payload


def generate_secret_key() -> str:
    """Ephemeral signing key (used only when AUTH_SECRET_KEY is not configured)."""
    return secrets.token_urlsafe(48)
