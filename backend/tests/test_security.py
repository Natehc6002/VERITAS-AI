"""Tests for stdlib password hashing and signed access tokens."""

import time

import pytest

from app.core.security import (
    DEFAULT_TOKEN_TTL_SECONDS,
    TokenError,
    create_access_token,
    generate_secret_key,
    hash_password,
    parse_access_token,
    verify_password,
)

SECRET = "test-secret-key"


class TestPasswords:
    def test_hash_then_verify_roundtrip(self):
        stored = hash_password("correct horse battery staple")
        assert stored.startswith("pbkdf2_sha256$")
        assert verify_password("correct horse battery staple", stored)

    def test_wrong_password_rejected(self):
        stored = hash_password("right-password")
        assert not verify_password("wrong-password", stored)

    def test_hashes_are_salted(self):
        assert hash_password("same-password") != hash_password("same-password")

    @pytest.mark.parametrize(
        "stored",
        ["", "garbage", "pbkdf2_sha256$not-a-number$aa$bb", "md5$1$aa$bb", None],
    )
    def test_malformed_stored_hash_rejected(self, stored):
        assert not verify_password("anything", stored)


class TestTokens:
    def test_roundtrip_returns_subject(self):
        token = create_access_token("user-abc", SECRET)
        payload = parse_access_token(token, SECRET)
        assert payload["sub"] == "user-abc"
        assert payload["exp"] > int(time.time())

    def test_tampered_signature_rejected(self):
        token = create_access_token("user-abc", SECRET)
        version, body, signature = token.split(".")
        flipped = "A" if signature[-1] != "A" else "B"
        forged = f"{version}.{body}.{signature[:-1]}{flipped}"
        with pytest.raises(TokenError):
            parse_access_token(forged, SECRET)

    def test_tampered_payload_rejected(self):
        token = create_access_token("user-abc", SECRET)
        version, body, signature = token.split(".")
        other = create_access_token("victim-zzz", SECRET)
        other_body = other.split(".")[1]
        forged = f"{version}.{other_body}.{signature}"
        with pytest.raises(TokenError):
            parse_access_token(forged, SECRET)

    def test_wrong_secret_rejected(self):
        token = create_access_token("user-abc", SECRET)
        with pytest.raises(TokenError):
            parse_access_token(token, "different-secret")

    def test_expired_token_rejected(self):
        token = create_access_token("user-abc", SECRET, ttl_seconds=-10)
        with pytest.raises(TokenError):
            parse_access_token(token, SECRET)

    @pytest.mark.parametrize("bad_token", ["", "not-a-token", "v1.only-two", "v2.a.b", "x.y.z"])
    def test_malformed_tokens_rejected(self, bad_token):
        with pytest.raises(TokenError):
            parse_access_token(bad_token, SECRET)

    def test_empty_secret_refused(self):
        with pytest.raises(ValueError):
            create_access_token("user-abc", "")
        with pytest.raises(TokenError):
            parse_access_token("v1.a.b", "")

    def test_default_ttl_is_positive(self):
        assert DEFAULT_TOKEN_TTL_SECONDS > 0

    def test_generate_secret_key_unique(self):
        assert generate_secret_key() != generate_secret_key()
