"""PDF -> page images (PyMuPDF) and OCR (Tesseract). Distinguishes typed vs
scanned-handwritten pages by extractable-text density."""
from __future__ import annotations
import io
from pathlib import Path


def render_pages(pdf_path: str, out_dir: str, dpi: int = 300, prefix: str = "p") -> list[str]:
    import fitz  # PyMuPDF
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    paths = []
    for i in range(len(doc)):
        pix = doc[i].get_pixmap(dpi=dpi)
        p = f"{out_dir}/{prefix}{i + 1:03d}.png"
        pix.save(p)
        paths.append(p)
    return paths


def page_text_layer(pdf_path: str) -> list[str]:
    """Return embedded text per page (empty string for scanned pages)."""
    import fitz
    doc = fitz.open(pdf_path)
    return [(doc[i].get_text() or "") for i in range(len(doc))]


def ocr_pdf(pdf_path: str, dpi: int = 300, psm: int = 6) -> list[str]:
    """OCR every page; returns text per page. Falls back gracefully if a page
    has a usable embedded text layer (no OCR needed)."""
    import fitz
    import pytesseract
    from PIL import Image
    doc = fitz.open(pdf_path)
    out = []
    for i in range(len(doc)):
        embedded = doc[i].get_text() or ""
        if len(embedded.strip()) > 40:
            out.append(embedded)
            continue
        pix = doc[i].get_pixmap(dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        out.append(pytesseract.image_to_string(img, config=f"--psm {psm}"))
    return out
