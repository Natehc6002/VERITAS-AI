"""Authentication endpoint tests."""

from fastapi.testclient import TestClient

from app.api.deps import resolve_token_secret
from app.core.security import create_access_token
from app.main import create_app
from tests.conftest import auth_header, register_user


def test_register_returns_token_and_default_investigation(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "newuser@example.com", "password": "strong-password-1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "newuser@example.com"
    assert "password" not in body["user"] and "password_hash" not in body["user"]
    assert body["investigation"] is not None
    assert body["investigation"]["name"] == "My Investigation"

    me = client.get("/api/v1/auth/me", headers=auth_header(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["user"]["id"] == body["user"]["id"]
    assert len(me.json()["investigations"]) == 1


def test_register_duplicate_email_conflicts(client: TestClient) -> None:
    payload = {"email": "dup@example.com", "password": "strong-password-1"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]


def test_register_normalizes_email(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "  MixedCase@Example.COM ", "password": "strong-password-1"},
    )
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "mixedcase@example.com"


def test_register_rejects_weak_password(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register", json={"email": "weak@example.com", "password": "short"}
    )
    assert response.status_code == 422


def test_register_rejects_invalid_email(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register", json={"email": "not-an-email", "password": "strong-password-1"}
    )
    assert response.status_code == 422


def test_login_success_and_failure(client: TestClient) -> None:
    register_user(client, "login@example.com", "login-password-1")

    ok = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "login-password-1"},
    )
    assert ok.status_code == 200
    assert ok.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers=auth_header(ok.json()["access_token"]))
    assert me.status_code == 200

    bad_password = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "wrong-password"},
    )
    assert bad_password.status_code == 401

    unknown_email = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "whatever-password"},
    )
    assert unknown_email.status_code == 401
    assert "Invalid email or password" in unknown_email.json()["detail"]


def test_missing_token_rejected(client: TestClient) -> None:
    anonymous = TestClient(create_app())
    for path in ("/api/v1/auth/me", "/api/v1/documents", "/api/v1/stats"):
        response = anonymous.get(path)
        assert response.status_code == 401, path


def test_malformed_token_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me", headers=auth_header("garbage-token"))
    assert response.status_code == 401


def test_token_signed_with_wrong_secret_rejected(client: TestClient) -> None:
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    user_id = me.json()["user"]["id"]
    forged = create_access_token(user_id, "attacker-controlled-secret")
    response = client.get("/api/v1/auth/me", headers=auth_header(forged))
    assert response.status_code == 401


def test_expired_token_rejected(client: TestClient) -> None:
    me = client.get("/api/v1/auth/me")
    user_id = me.json()["user"]["id"]
    expired = create_access_token(
        user_id, resolve_token_secret(), ttl_seconds=-10
    )
    response = client.get("/api/v1/auth/me", headers=auth_header(expired))
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower() or "invalid" in response.json()[
        "detail"
    ].lower()


def test_endpoints_require_auth(client: TestClient) -> None:
    anonymous = TestClient(create_app())
    assert anonymous.get("/api/v1/documents").status_code == 401
    assert anonymous.post("/api/v1/documents/upload").status_code == 401
    assert anonymous.post(
        "/api/v1/compare", json={"document_ids": ["x", "y"]}
    ).status_code == 401
    assert anonymous.get("/api/v1/investigations").status_code == 401
    assert anonymous.get("/api/v1/health").status_code == 200
