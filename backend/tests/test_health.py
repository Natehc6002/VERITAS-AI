"""Health, documentation and CORS tests."""

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_documentation_available(client: TestClient) -> None:
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200

    schema = client.get("/openapi.json").json()
    assert "/api/v1/documents/upload" in schema["paths"]
    assert "/api/v1/documents" in schema["paths"]
    assert "/api/v1/documents/{document_id}" in schema["paths"]


def test_cors_allows_local_frontend_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/documents",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_blocks_unknown_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/documents",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None
