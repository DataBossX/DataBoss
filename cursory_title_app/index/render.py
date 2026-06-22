"""Render the scanned/handwritten index PDF to page images for vision models.

The Section 31 index has NO text layer (it is cursive handwriting), so this is
a hard requirement before any extraction can happen.
"""
from __future__ import annotations

from pathlib import Path

from .. import config


def render_pdf(pdf_path: Path, out_dir: Path = config.PAGES_DIR,
               scale: float = 2.5) -> list[Path]:
    """Render each PDF page to PNG. Returns the list of image paths in order."""
    import pypdfium2 as pdfium

    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(pdf_path))
    paths: list[Path] = []
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            bitmap = page.render(scale=scale)
            img = bitmap.to_pil()
            out = out_dir / f"index_p{i + 1:03d}.png"
            img.save(out)
            paths.append(out)
    finally:
        pdf.close()
    return paths


def page_count(pdf_path: Path) -> int:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        return len(pdf)
    finally:
        pdf.close()
