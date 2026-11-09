"""End-to-end journey test: register -> upload -> analyse -> investigate -> report."""

import pymupdf as fitz
from fastapi.testclient import TestClient

from tests.conftest import make_pdf_bytes


def test_full_investigation_workflow_with_pdf_report(
    client: TestClient, upload_file
) -> None:
    # 1. Register (performed by the client fixture); confirm session context.
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["investigations"], "default investigation expected"

    # 2. Upload a document.
    invoice_pdf = make_pdf_bytes(
        "INVOICE INV-2024-001\nBill to: accounts@northwind.example\n"
        "Total: USD 5,000.00\nDue: 2024-03-01\nPhone: +1-555-0100"
    )
    first = upload_file("invoice-march.pdf", invoice_pdf)
    assert first.status_code == 201, first.text
    doc_a = first.json()

    # 3. Extract document text.
    extraction = client.post(f"/api/v1/documents/{doc_a['id']}/extract")
    assert extraction.status_code == 200
    assert extraction.json()["status"] in ("completed", "no_text")

    # 4+5+6. Classification, entities and forensic analysis in one bundle.
    analysis = client.post(f"/api/v1/documents/{doc_a['id']}/analyze")
    assert analysis.status_code == 200
    bundle = analysis.json()
    assert bundle["classification"]["status"] == "completed"
    assert bundle["entities"], "expected extracted entities"
    assert isinstance(bundle["findings"], list)

    # Evidence-backed findings endpoints.
    findings = client.get(f"/api/v1/documents/{doc_a['id']}/findings").json()
    assert isinstance(findings, list)
    evidence = client.get(f"/api/v1/documents/{doc_a['id']}/evidence").json()
    assert isinstance(evidence, list)

    # 7. Create an investigation.
    created = client.post(
        "/api/v1/investigations",
        json={"name": "Quarterly fraud sweep", "description": "E2E demo case"},
    )
    assert created.status_code == 201
    investigation = created.json()

    # Move the first document into the investigation by re-uploading there is no
    # move endpoint; instead upload both documents directly into the case.
    filed = client.post(
        "/api/v1/documents/upload",
        files={"file": ("invoice-march.pdf", invoice_pdf, "application/pdf")},
        data={"investigation_id": investigation["id"]},
    )
    assert filed.status_code == 201, filed.text
    doc_a = filed.json()
    assert doc_a["investigation_id"] == investigation["id"]

    # 8. Add another document with a conflicting identifier.
    second_pdf = make_pdf_bytes(
        "INVOICE INV-2024-001\nBill to: billing@northwind.example\n"
        "Total: USD 7,500.00\nDue: 2024-03-15\nPhone: +1-555-0100"
    )
    second = client.post(
        "/api/v1/documents/upload",
        files={"file": ("invoice-april.pdf", second_pdf, "application/pdf")},
        data={"investigation_id": investigation["id"]},
    )
    assert second.status_code == 201, second.text
    doc_b = second.json()

    # 9. Compare documents.
    comparison = client.post(
        "/api/v1/compare", json={"document_ids": [doc_a["id"], doc_b["id"]]}
    )
    assert comparison.status_code == 200, comparison.text
    compare_body = comparison.json()
    assert compare_body["summary"]["documents_compared"] == 2

    # 10. Evidence-backed findings still served for the filed documents.
    findings_a = client.get(f"/api/v1/documents/{doc_a['id']}/findings")
    assert findings_a.status_code == 200

    # 11+12. Generate, download and inspect the PDF report.
    report = client.get(f"/api/v1/investigations/{investigation['id']}/report")
    assert report.status_code == 200, report.text[:300]
    assert report.headers["content-type"] == "application/pdf"
    assert "attachment" in report.headers.get("content-disposition", "")
    raw = report.content
    assert raw.startswith(b"%PDF"), "response is not a PDF"

    pdf = fitz.open(stream=raw, filetype="pdf")
    try:
        assert len(pdf) >= 2, "report should span multiple pages"
        text = "\n".join(page.get_text() for page in pdf)
    finally:
        pdf.close()

    # Cover / investigation details.
    assert "Forensic Investigation Report" in text
    assert "Quarterly fraud sweep" in text
    assert "E2E demo case" in text
    assert "tester@veritas.test" in text
    # Document information + hashes.
    assert "invoice-march.pdf" in text
    assert "invoice-april.pdf" in text
    assert doc_a["sha256_hash"][:32] in text.replace("\n", "")
    # Entities and findings sections.
    assert "Extracted entities" in text
    assert "Forensic findings and evidence" in text
    # Cross-document comparison.
    assert "Cross-document comparison" in text
    assert "Shared entities" in text
    # Source references / evidence traceability.
    assert "source:" in text
    # Methodology + disclaimer.
    assert "Methodology and limitations" in text

    # Ownership: another user cannot download this report.
    from tests.conftest import register_user  # noqa: PLC0415

    token_b = register_user(client, "report-foreign@example.com")
    forbidden = client.get(
        f"/api/v1/investigations/{investigation['id']}/report",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert forbidden.status_code == 404


def test_report_requires_authentication(client: TestClient) -> None:
    from tests.conftest import register_user  # noqa: PLC0415
    from fastapi.testclient import TestClient as _TC  # noqa: PLC0415
    from app.main import create_app  # noqa: PLC0415

    token = register_user(client, "report-auth@example.com")
    investigation_id = None
    me = client.get("/api/v1/auth/me").json()
    investigation_id = me["investigations"][0]["id"]

    anonymous = _TC(create_app())
    assert (
        anonymous.get(f"/api/v1/investigations/{investigation_id}/report").status_code
        == 401
    )
    # Sanity: authenticated request for the same investigation is not 401.
    response = client.get(f"/api/v1/investigations/{investigation_id}/report")
    assert response.status_code == 200
    assert token
