"""Fuzzy (near-match) entity sharing between documents."""

from fastapi.testclient import TestClient

from tests.conftest import make_pdf_bytes


def _upload(client: TestClient, filename: str, text: str) -> dict:
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, make_pdf_bytes(text), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_fuzzy_organization_match_is_reported(client: TestClient) -> None:
    doc_a = _upload(
        client,
        "supplier-a.pdf",
        "SUPPLIER AGREEMENT\nCounterparty: Global Trade Holdings Ltd\n"
        "Ref: AAA-111\nContact: ops@globaltrade.example",
    )
    doc_b = _upload(
        client,
        "supplier-b.pdf",
        "SUPPLIER AGREEMENT\nCounterparty: Global Trading Holdings Ltd\n"
        "Ref: BBB-222\nContact: ops@globaltrade.example",
    )

    response = client.post("/api/v1/compare", json={"document_ids": [doc_a["id"], doc_b["id"]]})
    assert response.status_code == 200, response.text
    body = response.json()

    assert "fuzzy_name_matching" in body["method"]
    fuzzy = [
        item
        for item in body["shared_entities"]
        if item.get("match_type") == "fuzzy"
    ]
    assert fuzzy, f"expected a fuzzy match, got: {body['shared_entities']}"
    entry = fuzzy[0]
    assert entry["entity_type"] == "organization"
    assert entry["similarity"] >= 0.80
    assert "Global Trade" in entry["value"]
    assert "Global Trading" in entry["fuzzy_variant"]
    assert "human review" in entry["explanation"]
    assert entry["document_count"] == 2
    assert body["summary"]["fuzzy_match_count"] >= 1

    exact = [item for item in body["shared_entities"] if item.get("match_type") == "exact"]
    assert exact, "exact shared values (e.g. email) should still be present"


def test_identical_values_stay_exact_not_fuzzy(client: TestClient) -> None:
    text = (
        "SUPPLIER AGREEMENT\nCounterparty: Global Trade Holdings Ltd\n"
        "Contact: ops@globaltrade.example"
    )
    doc_a = _upload(client, "same-a.pdf", text)
    doc_b = _upload(client, "same-b.pdf", text)

    response = client.post("/api/v1/compare", json={"document_ids": [doc_a["id"], doc_b["id"]]})
    assert response.status_code == 200
    body = response.json()

    org_entries = [
        item for item in body["shared_entities"] if item["entity_type"] == "organization"
    ]
    assert org_entries
    assert all(item["match_type"] == "exact" for item in org_entries)
    assert body["summary"]["fuzzy_match_count"] == 0
