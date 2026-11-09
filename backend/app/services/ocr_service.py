"""OCR backend discovery and interface.

The service exposes a small, stable interface so the rest of the application
never depends on a specific OCR engine:

* :func:`ocr_available` - report whether a usable engine was found.
* :func:`recognize_file` - run OCR over an image/PDF page image.

Backends are resolved lazily and only one engine is ever loaded. If no engine
is installed the functions degrade gracefully and report the exact dependency
that would need to be installed (see README -> Known limitations).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Engines are probed in this order. Only the first importable engine is used.
_ENGINE_ORDER = ("rapidocr_onnxruntime", "pytesseract")


@dataclass
class OcrPageResult:
    """OCR output for a single page/image."""

    text: str
    confidence: float | None = None
    # (text, confidence, bounding box) triples when the engine provides them
    blocks: list[dict] = field(default_factory=list)


class OcrBackend:
    """Minimal OCR engine contract."""

    name: str = "unknown"

    def recognize_image(self, image_path: Path) -> OcrPageResult:  # pragma: no cover
        raise NotImplementedError


class _RapidOcrBackend(OcrBackend):
    """Backend backed by rapidocr-onnxruntime (CPU, bundled models)."""

    name = "rapidocr-onnxruntime"

    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415  (lazy import)

        self._engine = RapidOCR()

    def recognize_image(self, image_path: Path) -> OcrPageResult:
        result, _elapsed = self._engine(str(image_path))
        if not result:
            return OcrPageResult(text="", confidence=None, blocks=[])
        lines: list[dict] = []
        parts: list[str] = []
        confidences: list[float] = []
        for item in result:
            # rapidocr returns [box, text, score]
            if len(item) >= 3:
                text, score = item[1], item[2]
            else:  # pragma: no cover - defensive
                text, score = str(item[0]), None
            parts.append(str(text))
            if isinstance(score, (int, float)):
                confidences.append(float(score))
            lines.append(
                {
                    "text": str(text),
                    "confidence": round(float(score), 4) if isinstance(score, (int, float)) else None,
                }
            )
        average = sum(confidences) / len(confidences) if confidences else None
        return OcrPageResult(
            text="\n".join(parts),
            confidence=round(average, 4) if average is not None else None,
            blocks=lines,
        )


class _TesseractBackend(OcrBackend):
    """Backend backed by the pytesseract package and a system Tesseract binary."""

    name = "pytesseract"

    def __init__(self) -> None:
        import pytesseract  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415  (required by pytesseract)

        self._pytesseract = pytesseract
        self._image = Image

    def recognize_image(self, image_path: Path) -> OcrPageResult:
        image = self._image.open(image_path)
        data = self._pytesseract.image_to_data(
            image, output_type=self._pytesseract.Output.DICT
        )
        lines: list[dict] = []
        parts: list[str] = []
        confidences: list[float] = []
        for text, conf in zip(data.get("text", []), data.get("conf", []), strict=False):
            text = str(text).strip()
            if not text:
                continue
            parts.append(text)
            try:
                value = float(conf)
            except (TypeError, ValueError):
                value = -1.0
            if value >= 0:
                confidences.append(value / 100.0)
            lines.append({"text": text, "confidence": round(max(value, 0.0) / 100.0, 4)})
        average = sum(confidences) / len(confidences) if confidences else None
        return OcrPageResult(
            text="\n".join(parts),
            confidence=round(average, 4) if average is not None else None,
            blocks=lines,
        )


_backend: OcrBackend | None = None
_resolved = False
_missing_reason = "OCR backend has not been probed yet."


def _resolve_backend() -> OcrBackend | None:
    global _backend, _resolved, _missing_reason
    if _resolved:
        return _backend

    reasons: list[str] = []
    for engine_name in _ENGINE_ORDER:
        try:
            if engine_name == "rapidocr_onnxruntime":
                _backend = _RapidOcrBackend()
            else:
                _backend = _TesseractBackend()
            _resolved = True
            logger.info("OCR backend resolved: %s", _backend.name)
            return _backend
        except Exception as exc:  # noqa: BLE001 - probe must never crash the app
            reasons.append(f"{engine_name}: {type(exc).__name__}: {exc}")
            _backend = None

    _missing_reason = (
        "No OCR engine is installed. Install one of: "
        "`pip install rapidocr-onnxruntime` (recommended, self-contained), "
        "or install Tesseract OCR for Windows plus `pip install pytesseract pillow`. "
        + ("Probe errors -> " + " | ".join(reasons) if reasons else "")
    )
    _resolved = True
    logger.warning("No OCR engine available: %s", _missing_reason)
    return None


def ocr_available() -> bool:
    """Return True when a usable OCR engine is present."""
    return _resolve_backend() is not None


def ocr_backend_name() -> str | None:
    backend = _resolve_backend()
    return backend.name if backend else None


def ocr_unavailable_reason() -> str:
    _resolve_backend()
    return _missing_reason


def recognize_file(path: Path) -> OcrPageResult:
    """Run OCR on an image file. Raises RuntimeError when no engine exists."""
    backend = _resolve_backend()
    if backend is None:
        raise RuntimeError(_missing_reason)
    return backend.recognize_image(path)


def reset_for_tests() -> None:
    """Clear the cached backend probe (used by the test suite)."""
    global _backend, _resolved, _missing_reason
    _backend = None
    _resolved = False
    _missing_reason = "OCR backend has not been probed yet."
