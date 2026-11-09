"""Classification, entity extraction, forensic indicators, evidence and stats."""

from fastapi.testclient import TestClient

from tests.conftest import make_pdf_bytes

INVOICE_TEXT = """INVOICE
Invoice No: INV-2024-0099
Bill To: Acme Robotics Pvt Ltd
Name: John Smith
Date: 2024-03-15
Email: accounts@acmerobotics.com
Phone: +1 415 555 0132

Item                       Qty     Amount
Industrial sensor          10      USD 1,250.00
Calibration service         1      USD 300.00

Total due: USD 1,550.00
Due date: 2024-04-15
Thank you for your business.
"""


def _analyze(client: TestClient, document_id: str) -> dict:
    response = client.post(f"/api/v1/documents/{document_id}/analyze")
    assert response.status_code == 200, response.text
    return response.json()


def test_classify_invoice(client: TestClient, upload_file) -> None:
    document_id = upload_file("invoice.pdf", make_pdf_bytes(INVOICE_TEXT)).json()["id"]
    bundle = _analyze(client, document_id)

    classification = bundle["classification"]
    assert classification["status"] == "completed"
    assert classification["category"] == "invoice"
    assert classification["method"] == "rule_based_baseline"
    assert classification["confidence"] > 0
    assert classification["rationale"], "classification must record which rules fired"
    assert any("invoice" in item["rule"].lower() for item in classification["rationale"])


def test_extract_entities_from_invoice(client: TestClient, upload_file) -> None:
    document_id = upload_file("invoice.pdf", make_pdf_bytes(INVOICE_TEXT)).json()["id"]
    bundle = _analyze(client, document_id)

    entities = bundle["entities"]
    types = {e["entity_type"] for e in entities}
    assert "email" in types
    assert "money" in types
    assert "date" in types
    assert "document_identifier" in types
    assert "person_name" in types

    email = next(e for e in entities if e["entity_type"] == "email")
    assert email["value"] == "accounts@acmerobotics.com"
    assert email["page_number"] == 1
    assert email["source_text"]

    money = next(e for e in entities if e["entity_type"] == "money")
    assert money["normalized_value"] is not None

    dates = [e for e in entities if e["entity_type"] == "date"]
    assert any(e["normalized_value"] == "2024-03-15" for e in dates)


def test_entity_listing_endpoint(client: TestClient, upload_file) -> None:
    document_id = upload_file("invoice.pdf", make_pdf_bytes(INVOICE_TEXT)).json()["id"]
    _analyze(client, document_id)

    response = client.get(f"/api/v1/documents/{document_id}/entities")
    assert response.status_code == 200
    data = response.json()
    assert data
    assert {"entity_type", "value", "confidence", "source_text"} <= set(data[0])


def test_summary_is_factual(client: TestClient, upload_file) -> None:
    document_id = upload_file("invoice.pdf", make_pdf_bytes(INVOICE_TEXT)).json()["id"]
    bundle = _analyze(client, document_id)

    summary = bundle["summary"]
    assert summary
    assert "invoice" in summary.lower()
    assert "not determinations of fraud" in summary or "human review" in summary


def test_timestamp_anomaly_finding_with_evidence(client: TestClient, upload_file) -> None:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), INVOICE_TEXT)
    document.set_metadata(
        {
            "title": "Backdated invoice",
            "creationDate": "D:20240601000000Z",
            "modDate": "D:20240101000000Z",
        }
    )
    pdf_bytes = document.tobytes()
    document.close()

    document_id = upload_file("backdated.pdf", pdf_bytes).json()["id"]
    bundle = _analyze(client, document_id)

    findings = bundle["findings"]
    anomaly = next((f for f in findings if f["category"] == "timestamp_anomaly"), None)
    assert anomaly is not None, [f["category"] for f in findings]
    assert anomaly["severity"] == "medium"
    assert "earlier" in anomaly["explanation"]
    assert anomaly["detection_method"] == "pdf_date_relationship_check"
    assert len(anomaly["evidence"]) >= 2
    assert all(ev["source_ref"] and ev["explanation"] for ev in anomaly["evidence"])


def test_findings_endpoint(client: TestClient, upload_file) -> None:
    document_id = upload_file("plain.pdf", make_pdf_bytes("A short document.")).json()["id"]
    _analyze(client, document_id)

    response = client.get(f"/api/v1/documents/{document_id}/findings")
    assert response.status_code == 200
    for finding in response.json():
        assert finding["title"]
        assert finding["explanation"]
        assert finding["detection_method"]


def test_evidence_endpoint(client: TestClient, upload_file) -> None:
    document_id = upload_file("plain.pdf", make_pdf_bytes("A short document.")).json()["id"]
    _analyze(client, document_id)

    response = client.get(f"/api/v1/documents/{document_id}/evidence")
    assert response.status_code == 200
    for item in response.json():
        assert item["evidence_type"]
        assert item["source_ref"]
        assert item["explanation"]


def test_get_analysis_runs_on_demand(client: TestClient, upload_file) -> None:
    document_id = upload_file("ondemand.pdf", make_pdf_bytes(INVOICE_TEXT)).json()["id"]
    response = client.get(f"/api/v1/documents/{document_id}/analysis")
    assert response.status_code == 200
    bundle = response.json()
    assert bundle["classification"]["category"] == "invoice"
    assert bundle["extraction"]["status"] == "completed"


def test_duplicate_upload_raises_duplicate_finding(client: TestClient, upload_file) -> None:
    content = make_pdf_bytes(INVOICE_TEXT)
    first = upload_file("copy-a.pdf", content).json()["id"]
    second = upload_file("copy-b.pdf", content).json()["id"]

    bundle = _analyze(client, second)
    categories = [f["category"] for f in bundle["findings"]]
    assert "duplicate_file" in categories

    # Re-analysing the first document must also see the duplicate.
    first_bundle = _analyze(client, first)
    assert "duplicate_file" in [f["category"] for f in first_bundle["findings"]]


def test_analysis_is_deterministic_on_rerun(client: TestClient, upload_file) -> None:
    document_id = upload_file("twice.pdf", make_pdf_bytes(INVOICE_TEXT)).json()["id"]
    first = _analyze(client, document_id)
    second = _analyze(client, document_id)

    assert first["classification"]["category"] == second["classification"]["category"]
    assert len(first["entities"]) == len(second["entities"])
    assert len(first["findings"]) == len(second["findings"])


def test_dashboard_statistics(client: TestClient, upload_file) -> None:
    assert client.get("/api/v1/stats").json()["total_documents"] == 0

    upload_file("a.pdf", make_pdf_bytes(INVOICE_TEXT))
    upload_file("b.pdf", make_pdf_bytes("Another document with enough text to extract easily."))
    second_id = upload_file("c.pdf", make_pdf_bytes(INVOICE_TEXT)).json()["id"]
    _analyze(client, second_id)

    data = client.get("/api/v1/stats").json()
    assert data["total_documents"] == 3
    assert data["processed_documents"] == 3
    assert data["failed_documents"] == 0
    assert data["total_findings"] >= 1
    assert data["total_entities"] >= 1
    assert len(data["recent_documents"]) == 3
    assert {k for k in data["recent_documents"][0]} == {
        "id",
        "original_filename",
        "file_extension",
        "upload_timestamp",
        "processing_status",
        "file_size",
    }


def test_delete_document_removes_intelligence_rows(
    client: TestClient, upload_file
) -> None:
    document_id = upload_file("doomed.pdf", make_pdf_bytes(INVOICE_TEXT)).json()["id"]
    _analyze(client, document_id)
    assert client.get(f"/api/v1/documents/{document_id}/entities").json()

    assert client.delete(f"/api/v1/documents/{document_id}").status_code == 200

    assert client.get(f"/api/v1/documents/{document_id}/analysis").status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}/entities").status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}/evidence").status_code == 404


def test_unanalysed_document_stats_and_endpoints_are_consistent(
    client: TestClient, upload_file
) -> None:
    document_id = upload_file("fresh.pdf", make_pdf_bytes(INVOICE_TEXT)).json()["id"]
    assert client.get(f"/api/v1/documents/{document_id}/findings").json() == []
    assert client.get(f"/api/v1/documents/{document_id}/evidence").json() == []
    assert client.get(f"/api/v1/documents/{document_id}/entities").json() == []
