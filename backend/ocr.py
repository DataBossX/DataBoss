"""Text extraction / OCR.

Replaces the original mock OCR with real extraction:
  * text-like files are decoded directly,
  * images are run through Tesseract (pytesseract) when it is available.

If image OCR is requested but Tesseract is not installed, a clear ``OCRError``
is raised so the caller can mark the document ``failed`` with a useful message
instead of silently returning fake text.
"""
import os
import time
from typing import Any, Dict, Optional

TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log", ".xml", ".html", ".htm", ".rtf"}
TEXT_CONTENT_TYPES = {
    "text/plain", "text/markdown", "text/csv", "text/tab-separated-values",
    "application/json", "text/xml", "application/xml", "text/html",
}
IMAGE_CONTENT_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp",
    "image/webp", "image/gif",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"}


class OCRError(Exception):
    """Raised when text cannot be extracted from a document."""


def _ext(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


def is_text(filename: str, content_type: Optional[str]) -> bool:
    return _ext(filename) in TEXT_EXTENSIONS or (content_type or "").split(";")[0].strip() in TEXT_CONTENT_TYPES


def is_image(filename: str, content_type: Optional[str]) -> bool:
    return _ext(filename) in IMAGE_EXTENSIONS or (content_type or "").split(";")[0].strip() in IMAGE_CONTENT_TYPES


def tesseract_available() -> bool:
    """True only if both the python binding and the tesseract binary exist."""
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        return False
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def supported(filename: str, content_type: Optional[str]) -> bool:
    return is_text(filename, content_type) or is_image(filename, content_type)


def _ocr_image(content: bytes) -> tuple[str, float]:
    try:
        import io

        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise OCRError(
            "Image OCR requires Pillow and pytesseract to be installed."
        ) from exc

    try:
        image = Image.open(io.BytesIO(content))
        image.load()
    except Exception as exc:
        raise OCRError(f"Could not decode image: {exc}") from exc

    try:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError as exc:
        raise OCRError(
            "Tesseract OCR engine is not installed on this host."
        ) from exc
    except Exception as exc:
        raise OCRError(f"OCR failed: {exc}") from exc

    words = [w for w in data.get("text", []) if w and w.strip()]
    confidences = [float(c) for c in data.get("conf", []) if str(c) not in ("-1", "")]
    raw_text = " ".join(words)
    # pytesseract confidences are 0-100; normalise to 0-1.
    confidence = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
    return raw_text, round(confidence, 4)


def extract_text(content: bytes, filename: str, content_type: Optional[str]) -> Dict[str, Any]:
    """Extract text from a document. Raises OCRError on unsupported/failed input."""
    start = time.monotonic()

    if is_text(filename, content_type):
        raw_text = content.decode("utf-8", errors="replace")
        confidence = 1.0
        engine = "text-decode"
    elif is_image(filename, content_type):
        raw_text, confidence = _ocr_image(content)
        engine = "tesseract"
    else:
        raise OCRError(
            f"Unsupported file type for OCR: {content_type or _ext(filename) or 'unknown'}"
        )

    processing_time = time.monotonic() - start
    return {
        "raw_text": raw_text,
        "cleaned_text": raw_text.strip(),
        "confidence_score": confidence,
        "processing_time": processing_time,
        "ocr_engine": engine,
    }
