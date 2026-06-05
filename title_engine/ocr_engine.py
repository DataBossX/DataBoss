"""
OCR Engine — extracts text from PDF instrument images.

Priority order:
  1. pdfplumber  (fast, works on digital/text PDFs)
  2. PyMuPDF     (fitz) page-to-image + pytesseract (scanned fallback)
  3. Claude vision API (optional, best accuracy on difficult scans)

Saves <filename>.txt alongside each PDF.
"""

import io
import logging
import os
import re
from pathlib import Path
from typing import Optional, Tuple

log = logging.getLogger(__name__)


# ── Digital text extraction ───────────────────────────────────────────────────

def _try_pdfplumber(pdf_path: Path) -> Optional[str]:
    try:
        import pdfplumber
        texts = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    texts.append(t)
        combined = "\n\n".join(texts).strip()
        return combined if len(combined) > 30 else None
    except Exception as e:
        log.debug("pdfplumber failed: %s", e)
        return None


# ── Raster OCR fallback ───────────────────────────────────────────────────────

def _pdf_to_images(pdf_path: Path, dpi: int = 200):
    """Yields (page_num, PIL Image) using PyMuPDF."""
    import fitz
    doc = fitz.open(str(pdf_path))
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        from PIL import Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        yield i + 1, img
    doc.close()


def _try_tesseract(pdf_path: Path) -> Optional[str]:
    try:
        import pytesseract
        texts = []
        for _, img in _pdf_to_images(pdf_path):
            texts.append(pytesseract.image_to_string(img, config="--oem 3 --psm 6"))
        combined = "\n\n".join(texts).strip()
        return combined if len(combined) > 30 else None
    except Exception as e:
        log.debug("tesseract failed: %s", e)
        return None


# ── Claude vision (optional) ─────────────────────────────────────────────────

def _try_claude_vision(pdf_path: Path, api_key: str) -> Optional[str]:
    """Use Claude 3 Haiku vision to OCR difficult pages."""
    try:
        import base64
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        texts = []
        for page_num, img in _pdf_to_images(pdf_path, dpi=150):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode()

            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "This is a scanned page from an Oklahoma county land record instrument. "
                                "Transcribe ALL text exactly as it appears, preserving layout, "
                                "line breaks, capitalization, and spacing. "
                                "Include every word, number, and punctuation mark. "
                                "Output only the transcribed text — no commentary."
                            ),
                        },
                    ],
                }],
            )
            texts.append(msg.content[0].text)

        return "\n\n--- PAGE BREAK ---\n\n".join(texts).strip() or None
    except Exception as e:
        log.debug("Claude vision failed: %s", e)
        return None


# ── Post-processing ───────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove NUL bytes
    text = text.replace("\x00", "")
    return text.strip()


# ── Public API ────────────────────────────────────────────────────────────────

def ocr_pdf(pdf_path: Path, anthropic_key: str = None) -> Tuple[str, str]:
    """
    Extract text from a PDF.
    Returns (text, method_used).
    Saves <pdf_path>.txt automatically.
    """
    txt_path = pdf_path.with_suffix(".txt")

    # Already done?
    if txt_path.exists():
        existing = txt_path.read_text(encoding="utf-8", errors="replace").strip()
        if existing:
            return existing, "cached"

    text: Optional[str] = None
    method = "unknown"

    # 1 – pdfplumber (digital PDF)
    text = _try_pdfplumber(pdf_path)
    if text:
        method = "pdfplumber"

    # 2 – tesseract (scanned)
    if not text:
        text = _try_tesseract(pdf_path)
        if text:
            method = "tesseract"

    # 3 – Claude vision (optional, best quality)
    if not text and anthropic_key:
        text = _try_claude_vision(pdf_path, anthropic_key)
        if text:
            method = "claude_vision"

    if not text:
        text = "[OCR FAILED — NO TEXT EXTRACTED]"
        method = "failed"

    text = _clean_text(text)
    txt_path.write_text(text, encoding="utf-8")
    log.info("OCR %s → %s chars via %s", pdf_path.name, len(text), method)
    return text, method


def get_cached_text(pdf_path: Path) -> Optional[str]:
    txt_path = pdf_path.with_suffix(".txt")
    if txt_path.exists():
        t = txt_path.read_text(encoding="utf-8", errors="replace").strip()
        return t or None
    return None
