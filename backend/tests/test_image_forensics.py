"""Image EXIF metadata forensics (JPEG/PNG provenance indicators)."""

import io
from typing import Any, Callable

from PIL import ExifTags, Image
from fastapi.testclient import TestClient

TAGS_BY_NAME = {name: identifier for identifier, name in ExifTags.TAGS.items()}


def _jpeg_bytes(exif_values: dict[str, str]) -> bytes:
    image = Image.new("RGB", (16, 16), (240, 240, 240))
    exif = image.getexif()
    for name, value in exif_values.items():
        exif[TAGS_BY_NAME[name]] = value
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def _png_bytes() -> bytes:
    image = Image.new("RGB", (16, 16), (240, 240, 240))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _analysis_findings(
    client: TestClient, upload_file: Callable[..., Any], document_id: str
) -> list[dict[str, Any]]:
    response = client.get(f"/api/v1/documents/{document_id}/analysis")
    assert response.status_code == 200, response.text
    return response.json()["findings"]


def test_jpeg_exif_produces_provenance_finding(
    client: TestClient, upload_file: Callable[..., Any]
) -> None:
    payload = _jpeg_bytes(
        {
            "Make": "VeritasCam",
            "Model": "X100",
            "Software": "UnitTest 1.0",
            "DateTime": "2024:01:01 10:00:00",
        }
    )
    response = upload_file("photo.jpg", payload, "image/jpeg")
    assert response.status_code == 201, response.text
    document_id = response.json()["id"]

    findings = _analysis_findings(client, upload_file, document_id)
    present = next(
        (f for f in findings if f["category"] == "exif_metadata_present"), None
    )
    assert present is not None, [f["category"] for f in findings]
    assert present["detection_method"] == "image_exif_field_read"

    excerpts = {item["excerpt"] for item in present["evidence"]}
    assert "VeritasCam" in excerpts
    assert "UnitTest 1.0" in excerpts
    source_refs = {item["source_ref"] for item in present["evidence"]}
    assert "image_exif.Make" in source_refs

    assert not any(
        f["detection_method"] == "image_exif_future_date_check" for f in findings
    )


def test_jpeg_future_exif_date_raises_timestamp_anomaly(
    client: TestClient, upload_file: Callable[..., Any]
) -> None:
    payload = _jpeg_bytes({"DateTime": "2999:01:01 10:00:00"})
    response = upload_file("future.jpg", payload, "image/jpeg")
    assert response.status_code == 201, response.text

    findings = _analysis_findings(client, upload_file, response.json()["id"])
    anomaly = next(
        (f for f in findings if f["detection_method"] == "image_exif_future_date_check"),
        None,
    )
    assert anomaly is not None, [f["category"] for f in findings]
    assert anomaly["severity"] == "low"
    assert anomaly["evidence"][0]["source_ref"] == "image_exif.DateTime"
    assert "2999" in anomaly["evidence"][0]["excerpt"]


def test_png_without_exif_reports_missing_metadata(
    client: TestClient, upload_file: Callable[..., Any]
) -> None:
    response = upload_file("plain.png", _png_bytes(), "image/png")
    assert response.status_code == 201, response.text

    findings = _analysis_findings(client, upload_file, response.json()["id"])
    missing = next(
        (f for f in findings if f["detection_method"] == "image_exif_field_presence"),
        None,
    )
    assert missing is not None, [f["category"] for f in findings]
    assert missing["category"] == "missing_metadata"
    assert "no EXIF" in missing["title"]
