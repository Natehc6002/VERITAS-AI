"""Cross-user isolation tests: documents, analysis, stats and investigations."""

from fastapi.testclient import TestClient

from tests.conftest import auth_header, make_pdf_bytes, register_user, upload_file


def _upload_as(client: TestClient, token: str, filename: str, content: bytes) -> dict:
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, content, "application/octet-stream")},
        headers=auth_header(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_documents_list_is_scoped(client: TestClient, upload_file) -> None:
    token_b = register_user(client, "isolation-b@example.com")
    upload_file("a-doc.pdf", make_pdf_bytes("owner A document"))
    _upload_as(client, token_b, "b-doc.pdf", make_pdf_bytes("owner B document"))

    list_a = client.get("/api/v1/documents").json()
    list_b = client.get("/api/v1/documents", headers=auth_header(token_b)).json()
    assert list_a["total"] == 1
    assert list_a["items"][0]["original_filename"] == "a-doc.pdf"
    assert list_b["total"] == 1
    assert list_b["items"][0]["original_filename"] == "b-doc.pdf"


def test_foreign_document_returns_404_everywhere(client: TestClient, upload_file) -> None:
    token_b = register_user(client, "isolation-c@example.com")
    document = upload_file("secret.pdf", make_pdf_bytes("private content")).json()
    other_foreign = upload_file("secret2.pdf", make_pdf_bytes("private content 2")).json()
    document_id = document["id"]
    headers = auth_header(token_b)

    assert client.get(f"/api/v1/documents/{document_id}", headers=headers).status_code == 404
    assert client.delete(f"/api/v1/documents/{document_id}", headers=headers).status_code == 404
    assert (
        client.post(f"/api/v1/documents/{document_id}/extract", headers=headers).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/documents/{document_id}/text", headers=headers).status_code == 404
    )
    assert (
        client.post(f"/api/v1/documents/{document_id}/analyze", headers=headers).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/documents/{document_id}/analysis", headers=headers).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/documents/{document_id}/findings", headers=headers).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/documents/{document_id}/entities", headers=headers).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/documents/{document_id}/evidence", headers=headers).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/compare",
            json={"document_ids": [document_id, other_foreign["id"]]},
            headers=headers,
        ).status_code
        == 404
    )


def test_stats_are_scoped(client: TestClient, upload_file) -> None:
    token_b = register_user(client, "isolation-d@example.com")
    upload_file("one.pdf", make_pdf_bytes("first"))
    upload_file("two.pdf", make_pdf_bytes("second"))
    _upload_as(client, token_b, "other.pdf", make_pdf_bytes("other owner"))

    stats_a = client.get("/api/v1/stats").json()
    stats_b = client.get("/api/v1/stats", headers=auth_header(token_b)).json()
    assert stats_a["total_documents"] == 2
    assert stats_b["total_documents"] == 1
    assert all(
        item["original_filename"] != "other.pdf" for item in stats_a["recent_documents"]
    )


def test_duplicate_detection_is_owner_scoped(
    client: TestClient, upload_file
) -> None:
    token_b = register_user(client, "isolation-e@example.com")
    payload = make_pdf_bytes("byte-identical content for duplicate test")

    first = upload_file("copy-1.pdf", payload)
    upload_file("copy-2.pdf", payload)
    analysis = client.post(
        f"/api/v1/documents/{first.json()['id']}/analyze"
    ).json()
    categories = [finding["category"] for finding in analysis["findings"]]
    assert "duplicate_file" in categories

    other = _upload_as(client, token_b, "copy-b.pdf", payload)
    analysis_b = client.post(
        f"/api/v1/documents/{other['id']}/analyze", headers=auth_header(token_b)
    ).json()
    categories_b = [finding["category"] for finding in analysis_b["findings"]]
    assert "duplicate_file" not in categories_b


def test_investigation_crud_and_isolation(client: TestClient) -> None:
    token_b = register_user(client, "isolation-f@example.com")

    created = client.post(
        "/api/v1/investigations", json={"name": "Case 42", "description": "fraud ring"}
    )
    assert created.status_code == 201
    investigation = created.json()

    listed_a = client.get("/api/v1/investigations").json()
    listed_b = client.get(
        "/api/v1/investigations", headers=auth_header(token_b)
    ).json()
    ids_a = [item["id"] for item in listed_a]
    ids_b = [item["id"] for item in listed_b]
    assert investigation["id"] in ids_a
    assert len(ids_a) == 2  # default investigation + created one
    assert investigation["id"] not in ids_b
    assert len(ids_b) == 1  # only B's default investigation

    headers_b = auth_header(token_b)
    assert (
        client.get(f"/api/v1/investigations/{investigation['id']}", headers=headers_b).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/investigations/{investigation['id']}",
            json={"name": "hijacked"},
            headers=headers_b,
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/investigations/{investigation['id']}", headers=headers_b
        ).status_code
        == 404
    )

    updated = client.patch(
        f"/api/v1/investigations/{investigation['id']}", json={"name": "Case 43"}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Case 43"

    assert client.delete(f"/api/v1/investigations/{investigation['id']}").status_code == 200
    remaining = client.get("/api/v1/investigations").json()
    assert investigation["id"] not in [item["id"] for item in remaining]
    assert len(remaining) == 1  # the default investigation remains


def test_upload_into_foreign_investigation_rejected(
    client: TestClient, upload_file
) -> None:
    token_b = register_user(client, "isolation-g@example.com")
    investigation = client.post(
        "/api/v1/investigations", json={"name": "Private case"}
    ).json()

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sneaky.pdf", make_pdf_bytes("x"), "application/octet-stream")},
        data={"investigation_id": investigation["id"]},
        headers=auth_header(token_b),
    )
    assert response.status_code == 404

    own = upload_file(
        "allowed.pdf", make_pdf_bytes("y"), content_type="application/octet-stream"
    )
    assert own.status_code == 201
    assert own.json()["investigation_id"] is None


def test_list_filter_by_investigation(client: TestClient, upload_file) -> None:
    investigation = client.post("/api/v1/investigations", json={"name": "Filtered"}).json()
    client.post(
        "/api/v1/documents/upload",
        files={"file": ("filed.pdf", make_pdf_bytes("filed"), "application/octet-stream")},
        data={"investigation_id": investigation["id"]},
    )
    upload_file("unfiled.pdf", make_pdf_bytes("unfiled"))

    filed = client.get(
        "/api/v1/documents", params={"investigation_id": investigation["id"]}
    ).json()
    assert filed["total"] == 1
    assert filed["items"][0]["original_filename"] == "filed.pdf"
    assert filed["items"][0]["investigation_id"] == investigation["id"]
