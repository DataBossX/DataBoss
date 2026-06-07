"""ocr_engine -- OCR scanned/image PDFs when the toolchain is available.

Honesty contract: this module never invents text. If poppler (pdftoppm) and an
OCR backend (pytesseract/tesseract) are not present, it reports the document as
``ocr_status="unavailable"`` and returns no text, so downstream code logs a
limitation instead of fabricating content.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass
class OcrResult:
    source: str
    ocr_status: str          # "ok" | "unavailable" | "error" | "skipped"
    text: str = ""
    pages_processed: int = 0
    mean_confidence: int = 0
    detail: str = ""


def capabilities() -> dict:
    """Probe what OCR capabilities exist in this runtime."""
    have_poppler = shutil.which("pdftoppm") is not None
    have_tesseract = shutil.which("tesseract") is not None
    have_pytesseract = False
    have_fitz = False
    try:
        import pytesseract  # noqa: F401
        have_pytesseract = True
    except Exception:
        pass
    try:
        import fitz  # PyMuPDF  # noqa: F401
        have_fitz = True
    except Exception:
        pass
    return {
        "poppler": have_poppler,
        "tesseract": have_tesseract,
        "pytesseract": have_pytesseract,
        "pymupdf": have_fitz,
        "can_ocr": (have_fitz or have_poppler) and (have_tesseract and have_pytesseract),
    }


def ocr_pdf(path: str, max_pages: int = 25) -> OcrResult:
    caps = capabilities()
    if not caps["can_ocr"]:
        missing = [k for k in ("poppler", "tesseract", "pytesseract", "pymupdf") if not caps[k]]
        return OcrResult(
            source=path,
            ocr_status="unavailable",
            detail=f"OCR toolchain not installed (missing: {', '.join(missing)}). "
                   f"Image-only PDF left un-transcribed by design; not fabricated.",
        )
    # Real OCR path (used automatically when the toolchain is present).
    try:
        import fitz  # type: ignore
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
        import io

        doc = fitz.open(path)
        texts, confs, n = [], [], 0
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            page_text = " ".join(w for w in data["text"] if w.strip())
            page_conf = [int(c) for c in data["conf"] if str(c).lstrip("-").isdigit() and int(c) >= 0]
            texts.append(page_text)
            confs.extend(page_conf)
            n += 1
        mean_conf = int(sum(confs) / len(confs)) if confs else 0
        return OcrResult(
            source=path,
            ocr_status="ok",
            text="\n\n".join(texts),
            pages_processed=n,
            mean_confidence=mean_conf,
            detail=f"OCR'd {n} page(s).",
        )
    except Exception as exc:  # pragma: no cover - defensive
        return OcrResult(source=path, ocr_status="error", detail=f"OCR error: {exc}")
