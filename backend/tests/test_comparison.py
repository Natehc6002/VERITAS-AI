"""Cross-document comparison: shared entities, related records and conflicts."""

from fastapi.testclient import TestClient

from tests.conftest import make_pdf_bytes

DOC_A = """INVOICE
Invoice No: INV-2024-0099
Customer: Acme Robotics Pvt Ltd
Name: John Smith
Email: billing@acme.com
Total: USD 1,550.00
"""

DOC_B = """INVOICE
Invoice No: INV-2024-0100
Customer: Acme Robotics Pvt Ltd
Name: John Smith
Email: accounts@acme.com
Total: USD 2,100.00
"""

DOC_C = """Quarterly report for Acme Robotics Pvt Ltd
Prepared by: Jane Doe
"""


def _upload(client: TestClient, filename: str, text: str) -> str:
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, make_pdf_bytes(text), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _compare(client: TestClient, document_ids: list[str]) -> dict:
    response = client.post("/api/v1/compare", json={"document_ids": document_ids})
    assert response.status_code == 200, response.text
    return response.json()


def test_compare_requires_at_least_two_documents(client: TestClient, upload_file) -> None:
    document_id = upload_file("only.pdf", make_pdf_bytes(DOC_A)).json()["id"]
    response = client.post("/api/v1/compare", json={"document_ids": [document_id]})
    assert response.status_code == 422


def test_compare_unknown_document_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/compare",
        json={
            "document_ids": [
                "00000000-0000-0000-0000-000000000000",
                "11111111-1111-1111-1111-111111111111",
            ]
        },
    )
    assert response.status_code == 404


def test_compare_detects_shared_person(client: TestClient) -> None:
    id_a = _upload(client, "a.pdf", DOC_A)
    id_b = _upload(client, "b.pdf", DOC_B)

    report = _compare(client, [id_a, id_b])

    assert report["summary"]["documents_compared"] == 2
    people = [
        item for item in report["shared_entities"] if item["entity_type"] == "person_name"
    ]
    assert people, [i["entity_type"] for i in report["shared_entities"]]
    assert any("john smith" in item["normalized_value"] for item in people)
    assert people[0]["document_count"] == 2
    assert all(occ["document_id"] in {id_a, id_b} for occ in people[0]["occurrences"])
    assert report["method"] == "exact_normalized_matching+fuzzy_name_matching"
    assert "not proof of fraud" in report["disclaimer"]


def test_compare_detects_conflicting_invoice_identifiers(client: TestClient) -> None:
    id_a = _upload(client, "a.pdf", DOC_A)
    id_b = _upload(client, "b.pdf", DOC_B)

    report = _compare(client, [id_a, id_b])

    conflicts = report["conflicts"]
    identifier = next(
        (c for c in conflicts if c["conflict_type"] == "identifier_label_mismatch"), None
    )
    assert identifier is not None, conflicts
    assert identifier["field"] == "invoice"
    values = {v["value"].upper() for v in identifier["values"]}
    assert "INV-2024-0099" in values
    assert "INV-2024-0100" in values
    assert all(v["documents"] for v in identifier["values"])
    assert "Review in context" in identifier["explanation"]


def test_compare_detects_conflicting_contact_details(client: TestClient) -> None:
    id_a = _upload(client, "a.pdf", DOC_A)
    id_b = _upload(client, "b.pdf", DOC_B)

    report = _compare(client, [id_a, id_b])

    email_conflict = next(
        (c for c in report["conflicts"] if c["conflict_type"] == "person_contact_mismatch"),
        None,
    )
    assert email_conflict is not None, report["conflicts"]
    assert email_conflict["field"] == "email"
    assert email_conflict["subject"] == "john smith"
    emails = {v["value"] for v in email_conflict["values"]}
    assert "billing@acme.com" in emails
    assert "accounts@acme.com" in emails


def test_compare_identifies_related_records(client: TestClient) -> None:
    id_a = _upload(client, "a.pdf", DOC_A)
    id_b = _upload(client, "b.pdf", DOC_B)
    id_c = _upload(client, "c.pdf", DOC_C)

    report = _compare(client, [id_a, id_b, id_c])

    related = report["related_records"]
    pair = next(
        (
            r
            for r in related
            if set(r["document_ids"]) == {id_a, id_b}
        ),
        None,
    )
    assert pair is not None, related
    assert len(pair["shared_values"]) >= 2
    assert set(pair["document_names"]) == {"a.pdf", "b.pdf"}
    # Unrelated document must not be grouped with the others unless it shares values.
    for entry in related:
        assert len(entry["document_ids"]) == 2


def test_compare_runs_analysis_automatically(client: TestClient) -> None:
    id_a = _upload(client, "a.pdf", DOC_A)
    id_b = _upload(client, "b.pdf", DOC_B)

    report = _compare(client, [id_a, id_b])
    assert report["summary"]["shared_entity_count"] >= 1

    # Analysis rows now exist, so the analysis endpoint returns content directly.
    bundle = client.get(f"/api/v1/documents/{id_a}/analysis").json()
    assert bundle["entities"]


def test_compare_with_deduplicated_ids_rejected(client: TestClient) -> None:
    document_id = _upload(client, "a.pdf", DOC_A)
    response = client.post(
        "/api/v1/compare", json={"document_ids": [document_id, document_id]}
    )
    assert response.status_code == 422
