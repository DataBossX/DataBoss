"""Multi-fallback OCR engine for landman pipeline.

Fallback order:
  1. pdfplumber  — text-layer PDF extraction (free, instant)
  2. GPT-4o      — high-quality vision OCR
  3. Gemini 1.5  — cheaper long-context fallback
  4. Tesseract   — free offline fallback
"""

import base64
import json
import os
from pathlib import Path
from typing import Optional

from loguru import logger

# ── optional dependencies ──────────────────────────────────────────────────────
try:
    import pdfplumber
    _HAS_PDFPLUMBER = True
except ImportError:
    _HAS_PDFPLUMBER = False

try:
    import pytesseract
    from PIL import Image as PILImage
    _HAS_TESSERACT = True
except ImportError:
    _HAS_TESSERACT = False


def _load_openai():
    from openai import OpenAI
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        return None
    return OpenAI(api_key=key)


def _load_gemini():
    import google.generativeai as genai
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        return None
    genai.configure(api_key=key)
    return genai.GenerativeModel("gemini-1.5-flash")


def _file_to_b64(path: str) -> tuple[str, str]:
    """Returns (b64_string, mime_type)."""
    suffix = Path(path).suffix.lower()
    mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".tiff": "image/tiff", ".tif": "image/tiff"}.get(suffix, "image/jpeg")
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode(), mime


# ── strategy 1: pdfplumber ─────────────────────────────────────────────────────

def _pdfplumber_extract(pdf_path: str) -> Optional[dict]:
    if not _HAS_PDFPLUMBER:
        return None
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = []
            for p in pdf.pages:
                text = p.extract_text() or ""
                pages.append(text)
            full_text = "\n\n".join(pages).strip()
            if not full_text or len(full_text) < 50:
                return None  # likely scanned — no text layer
            char_count = sum(len(t) for t in pages)
            confidence = min(0.95, 0.6 + (char_count / 5000) * 0.35)
            return {
                "text": full_text,
                "confidence": round(confidence, 3),
                "method": "pdfplumber",
                "pages": len(pages),
                "cost": 0.0,
            }
    except Exception as e:
        logger.warning(f"pdfplumber failed on {pdf_path}: {e}")
        return None


# ── strategy 2: GPT-4o vision ─────────────────────────────────────────────────

def _gpt4o_extract(image_paths: list[str]) -> Optional[dict]:
    client = _load_openai()
    if not client:
        return None
    try:
        content = [{
            "type": "text",
            "text": (
                "You are an expert document scanner. Extract ALL readable text from "
                "this land record document image exactly as it appears, preserving "
                "line breaks and formatting. Output raw text only."
            ),
        }]
        for p in image_paths[:5]:
            b64, mime = _file_to_b64(p)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
            })

        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=4096,
        )
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        cost = (usage.prompt_tokens * 2.50 + usage.completion_tokens * 10.0) / 1_000_000
        return {
            "text": text,
            "confidence": 0.92,
            "method": "gpt-4o",
            "pages": len(image_paths),
            "cost": round(cost, 6),
        }
    except Exception as e:
        logger.warning(f"GPT-4o OCR failed: {e}")
        return None


# ── strategy 3: Gemini 1.5 Flash vision ───────────────────────────────────────

def _gemini_extract(image_paths: list[str]) -> Optional[dict]:
    model = _load_gemini()
    if not model:
        return None
    try:
        from PIL import Image as PILImage
        images = [PILImage.open(p) for p in image_paths[:10]]
        prompt = (
            "Extract ALL readable text from this land record document image exactly "
            "as it appears, preserving structure. Output raw text only."
        )
        resp = model.generate_content([prompt, *images])
        text = resp.text or ""
        # Gemini 1.5 Flash: ~$0.075/1M input tokens (approximate)
        return {
            "text": text,
            "confidence": 0.85,
            "method": "gemini-1.5-flash",
            "pages": len(image_paths),
            "cost": 0.0002,  # rough estimate per document
        }
    except Exception as e:
        logger.warning(f"Gemini OCR failed: {e}")
        return None


# ── strategy 4: Tesseract ──────────────────────────────────────────────────────

def _tesseract_extract(image_paths: list[str]) -> Optional[dict]:
    if not _HAS_TESSERACT:
        return None
    try:
        pages = []
        for p in image_paths:
            img = PILImage.open(p)
            text = pytesseract.image_to_string(img, config="--psm 6")
            pages.append(text)
        full_text = "\n\n".join(pages).strip()
        return {
            "text": full_text,
            "confidence": 0.70,
            "method": "tesseract",
            "pages": len(image_paths),
            "cost": 0.0,
        }
    except Exception as e:
        logger.warning(f"Tesseract OCR failed: {e}")
        return None


# ── public API ─────────────────────────────────────────────────────────────────

def extract_text(file_path: str, image_paths: Optional[list[str]] = None) -> dict:
    """
    Extract text from a document file using the best available method.

    Args:
        file_path: Path to the source file (PDF, image, etc.)
        image_paths: Pre-rendered image pages for PDFs (optional; used for vision APIs)

    Returns:
        dict with keys: text, confidence, method, pages, cost
    """
    path = Path(file_path)
    is_pdf = path.suffix.lower() == ".pdf"

    # Strategy 1: pdfplumber for text-layer PDFs
    if is_pdf:
        result = _pdfplumber_extract(file_path)
        if result and result["confidence"] >= 0.65:
            logger.info(f"OCR pdfplumber success: {path.name} conf={result['confidence']}")
            return result

    # Gather image paths for vision APIs
    vision_targets = image_paths or ([file_path] if not is_pdf else [])

    # Strategy 2: GPT-4o vision
    if vision_targets:
        result = _gpt4o_extract(vision_targets)
        if result:
            logger.info(f"OCR gpt-4o success: {path.name} cost=${result['cost']:.4f}")
            return result

    # Strategy 3: Gemini vision
    if vision_targets:
        result = _gemini_extract(vision_targets)
        if result:
            logger.info(f"OCR gemini success: {path.name}")
            return result

    # Strategy 4: Tesseract
    if vision_targets:
        result = _tesseract_extract(vision_targets)
        if result:
            logger.info(f"OCR tesseract success: {path.name}")
            return result

    logger.error(f"All OCR strategies failed for {path.name}")
    return {
        "text": "",
        "confidence": 0.0,
        "method": "none",
        "pages": 0,
        "cost": 0.0,
        "error": "All OCR strategies failed",
    }


def pdf_to_images(pdf_path: str, dpi: int = 200) -> list[str]:
    """Convert a PDF to a list of JPEG image paths using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        stem = Path(pdf_path).stem
        out_dir = Path(pdf_path).parent / f"{stem}_pages"
        out_dir.mkdir(exist_ok=True)
        paths = []
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=mat)
            out = str(out_dir / f"page_{i+1:03d}.jpg")
            pix.save(out)
            paths.append(out)
        doc.close()
        return paths
    except Exception as e:
        logger.error(f"pdf_to_images failed: {e}")
        return []
