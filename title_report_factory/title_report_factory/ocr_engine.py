"""Text extraction and OCR.

Strategy per file:
  * PDF  -> extract embedded text (PyMuPDF). If a page has little/no text and
            OCR is available, rasterize and OCR it.
  * image -> OCR directly (if available).
  * text/csv -> read as-is.
  * excel -> handled by the index_builder/file readers, not here.

Every dependency is optional and probed at runtime; nothing crashes the run if
a backend is missing -- it degrades and records the limitation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from .utils import LOG

# --- optional backends, probed lazily -------------------------------------
try:
    import fitz  # PyMuPDF
    _HAVE_FITZ = True
except Exception:  # pragma: no cover
    _HAVE_FITZ = False

try:
    import pytesseract  # noqa: F401
    from PIL import Image  # noqa: F401
    import shutil
    _HAVE_TESS = shutil.which("tesseract") is not None
except Exception:  # pragma: no cover
    _HAVE_TESS = False


@dataclass
class ExtractedText:
    text: str = ""
    ocr_used: bool = False
    ocr_confidence: Optional[float] = None
    pages: int = 0
    backends: List[str] = field(default_factory=list)
    note: str = ""


def backends_available() -> List[str]:
    found = []
    if _HAVE_FITZ:
        found.append("pymupdf")
    if _HAVE_TESS:
        found.append("tesseract")
    return found


def _ocr_pixmap(pix) -> Tuple[str, float]:
    """OCR a PyMuPDF pixmap; returns (text, mean_word_confidence 0-100)."""
    import io

    from PIL import Image
    import pytesseract

    img = Image.open(io.BytesIO(pix.tobytes("png")))
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    words, confs = [], []
    for word, conf in zip(data["text"], data["conf"]):
        word = (word or "").strip()
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            conf = -1
        if word and conf >= 0:
            words.append(word)
            confs.append(conf)
    mean_conf = sum(confs) / len(confs) if confs else 0.0
    return " ".join(words), mean_conf


def extract_text(path: Path, enable_ocr: bool = True) -> ExtractedText:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path, enable_ocr)
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"}:
        return _extract_image(path, enable_ocr)
    if suffix in {".txt", ".md", ".csv", ".json"}:
        try:
            return ExtractedText(
                text=path.read_text(encoding="utf-8", errors="ignore"),
                backends=["plaintext"],
            )
        except OSError as exc:
            return ExtractedText(note=f"read error: {exc}")
    return ExtractedText(note=f"unsupported for OCR: {suffix}")


def _extract_pdf(path: Path, enable_ocr: bool) -> ExtractedText:
    if not _HAVE_FITZ:
        return ExtractedText(note="PyMuPDF not installed; cannot read PDF")
    out = ExtractedText(backends=["pymupdf"])
    ocr_confs: List[float] = []
    try:
        with fitz.open(path) as doc:
            out.pages = doc.page_count
            chunks = []
            for page in doc:
                txt = page.get_text("text") or ""
                # If the page is essentially empty, try OCR.
                if len(txt.strip()) < 20 and enable_ocr and _HAVE_TESS:
                    try:
                        pix = page.get_pixmap(dpi=300)
                        otext, oconf = _ocr_pixmap(pix)
                        if otext.strip():
                            txt = otext
                            out.ocr_used = True
                            ocr_confs.append(oconf)
                            if "tesseract" not in out.backends:
                                out.backends.append("tesseract")
                    except Exception as exc:  # pragma: no cover
                        LOG.debug("OCR failed on %s p?: %s", path.name, exc)
                chunks.append(txt)
            out.text = "\n".join(chunks)
    except Exception as exc:
        out.note = f"PDF read error: {exc}"
        return out
    if ocr_confs:
        out.ocr_confidence = sum(ocr_confs) / len(ocr_confs)
    if not out.text.strip() and not out.ocr_used:
        out.note = ("PDF has no embedded text and OCR is unavailable "
                    "(install tesseract) -- needs review")
    return out


def _extract_image(path: Path, enable_ocr: bool) -> ExtractedText:
    out = ExtractedText(backends=["image"])
    if not (enable_ocr and _HAVE_TESS):
        out.note = "image requires OCR but tesseract is unavailable"
        return out
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(path)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        words, confs = [], []
        for w, c in zip(data["text"], data["conf"]):
            w = (w or "").strip()
            try:
                c = float(c)
            except (TypeError, ValueError):
                c = -1
            if w and c >= 0:
                words.append(w)
                confs.append(c)
        out.text = " ".join(words)
        out.ocr_used = True
        out.ocr_confidence = sum(confs) / len(confs) if confs else 0.0
        out.pages = 1
        out.backends.append("tesseract")
    except Exception as exc:
        out.note = f"image OCR error: {exc}"
    return out
