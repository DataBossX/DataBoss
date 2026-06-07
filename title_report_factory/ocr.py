"""OCR and text extraction for scanned PDFs and images.

All heavy dependencies (pdfplumber, PyMuPDF, pytesseract, Pillow) are imported
lazily and guarded. If none are present the functions return an empty string
plus a clear status string, so the pipeline degrades honestly instead of
crashing or pretending it read a document.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple


@dataclass
class OCRResult:
    text: str
    status: str          # e.g. "extracted-text", "ocr-tesseract", "no-engine", "error"
    confidence: int      # 0-100, crude heuristic
    pages: int


def _heuristic_confidence(text: str) -> int:
    """Very rough quality score from character composition of OCR output."""
    if not text:
        return 0
    alpha = sum(c.isalnum() or c.isspace() for c in text)
    ratio = alpha / max(len(text), 1)
    length_factor = min(len(text) / 400.0, 1.0)
    return int(round(ratio * length_factor * 100))


def extract_pdf_text(path: str) -> OCRResult:
    """Try embedded text first (pdfplumber/PyMuPDF), then OCR fallback."""
    p = Path(path)
    if not p.exists():
        return OCRResult("", "missing-file", 0, 0)

    # 1) Embedded text via pdfplumber.
    try:
        import pdfplumber
        with pdfplumber.open(str(p)) as pdf:
            pages = pdf.pages
            text = "\n".join((pg.extract_text() or "") for pg in pages)
        if text.strip():
            return OCRResult(text, "extracted-text", _heuristic_confidence(text), len(pages))
    except ImportError:
        pass
    except Exception:
        pass

    # 2) Embedded text via PyMuPDF.
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(p))
        text = "\n".join(page.get_text() for page in doc)
        n = doc.page_count
        doc.close()
        if text.strip():
            return OCRResult(text, "extracted-text", _heuristic_confidence(text), n)
    except ImportError:
        pass
    except Exception:
        pass

    # 3) OCR fallback (render pages -> tesseract).
    ocr = _ocr_pdf_pages(p)
    if ocr is not None:
        return ocr

    return OCRResult("", "no-engine", 0, 0)


def _ocr_pdf_pages(p: Path) -> "OCRResult | None":
    try:
        import fitz
        import pytesseract
        from PIL import Image
        import io
    except ImportError:
        return None
    try:
        doc = fitz.open(str(p))
        chunks = []
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            img = _preprocess(img)
            chunks.append(pytesseract.image_to_string(img))
        n = doc.page_count
        doc.close()
        text = "\n".join(chunks)
        return OCRResult(text, "ocr-tesseract", _heuristic_confidence(text), n)
    except Exception:
        return OCRResult("", "error", 0, 0)


def extract_image_text(path: str) -> OCRResult:
    p = Path(path)
    if not p.exists():
        return OCRResult("", "missing-file", 0, 0)
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return OCRResult("", "no-engine", 0, 0)
    try:
        img = _preprocess(Image.open(str(p)))
        text = pytesseract.image_to_string(img)
        return OCRResult(text, "ocr-tesseract", _heuristic_confidence(text), 1)
    except Exception:
        return OCRResult("", "error", 0, 0)


def _preprocess(img):
    """Deskew-free preprocessing: grayscale + autocontrast + upscale small images."""
    try:
        from PIL import ImageOps
        img = img.convert("L")
        img = ImageOps.autocontrast(img)
        w, h = img.size
        if max(w, h) < 1600:
            scale = 1600 / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)))
        return img
    except Exception:
        return img
