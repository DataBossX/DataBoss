"""Rasterize + OCR PDFs and images. Uses PyMuPDF for rendering and Tesseract for OCR,
falling back to any embedded text layer when present."""
from __future__ import annotations
import io, os

def _configure_tesseract(cmd: str):
    if cmd:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = cmd


def ocr_pdf(path: str, dpi: int = 250, tesseract_cmd: str = "") -> dict[int, str]:
    """Return {page_number: text}. Uses embedded text if the page has it, else OCR."""
    import fitz  # PyMuPDF
    _configure_tesseract(tesseract_cmd)
    out: dict[int, str] = {}
    doc = fitz.open(path)
    for i in range(doc.page_count):
        page = doc[i]
        txt = page.get_text().strip()
        if len(txt) < 25:  # scanned page -> OCR
            import pytesseract
            from PIL import Image
            pix = page.get_pixmap(dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            txt = pytesseract.image_to_string(img)
        out[i + 1] = txt
    return out


def ocr_image(path: str, tesseract_cmd: str = "") -> str:
    import pytesseract
    from PIL import Image
    _configure_tesseract(tesseract_cmd)
    return pytesseract.image_to_string(Image.open(path))


def ocr_any(path: str, tesseract_cmd: str = "") -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return "\n".join(ocr_pdf(path, tesseract_cmd=tesseract_cmd).values())
    return ocr_image(path, tesseract_cmd=tesseract_cmd)
