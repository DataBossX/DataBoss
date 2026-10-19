"""Candidate document-boundary detection for BLM case PDFs.

Every detection is a CANDIDATE. This module never emits a verified status:
a machine-detected boundary becomes evidence only after a human/vision
review of the original page image, which is a separate step.

Signals (embedded text only, unless --ocr is given):
- first physical page (jacket position)
- text containing "Page 1 of N"
- a form/document title as the first text line of a page

Image-only PDFs (no usable embedded text and no OCR) produce exactly one
row: status=NEEDS_VISION_QUEUE with the page count.

CLI: python -m peaches.boundaries <pdf_or_dir> <out_csv> [--ocr]
"""
from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile

try:
    import pymupdf as _pdf
except ImportError:
    import fitz as _pdf

PAGE_1_OF = re.compile(r"page\s+1\s+of\s+\d+", re.IGNORECASE)
TITLE_KEYWORDS = (
    "OIL AND GAS LEASE", "ASSIGNMENT", "AGREEMENT", "CERTIFICATE",
    "APPLICATION", "NOTICE", "MEMORANDUM", "DEED", "RELEASE",
    "COMMUNITIZATION", "UNIT AGREEMENT", "DECISION", "APPROVAL",
    "TRANSFER", "STIPULATION", "LEASE RECORD", "SERIAL REGISTER",
)

FIELDS = ["pdf", "page", "pages_total", "signal", "confidence", "status"]


def _ocr_page_text(doc, page_index, dpi=200):
    """Optional OCR hook. Guarded: returns '' when tesseract is unavailable
    or anything fails. OCR output is locator evidence only."""
    if shutil.which("tesseract") is None:
        return ""
    try:
        page = doc[page_index]
        pix = page.get_pixmap(dpi=dpi)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            pix.save(tmp.name)
            png = tmp.name
        try:
            out = subprocess.run(
                ["tesseract", png, "stdout", "--psm", "6"],
                capture_output=True, text=True, timeout=120)
            return out.stdout or ""
        finally:
            os.unlink(png)
    except Exception:
        return ""


def page_texts(path, use_ocr=False):
    doc = _pdf.open(path)
    try:
        texts = []
        ocr_used = False
        for i in range(doc.page_count):
            text = doc[i].get_text()
            if use_ocr and not text.strip():
                ocr_text = _ocr_page_text(doc, i)
                if ocr_text.strip():
                    ocr_used = True
                    text = ocr_text
            texts.append(text)
        return texts, ocr_used
    finally:
        doc.close()


def detect_boundaries(path, use_ocr=False):
    """Return a list of boundary rows for one PDF."""
    texts, ocr_used = page_texts(path, use_ocr=use_ocr)
    pages_total = len(texts)
    total_chars = sum(len(t.strip()) for t in texts)
    name = os.path.basename(path)
    if total_chars < 20:
        return [{
            "pdf": name, "page": "", "pages_total": pages_total,
            "signal": "IMAGE_ONLY_NO_TEXT_LAYER", "confidence": "",
            "status": "NEEDS_VISION_QUEUE",
        }]
    suffix = "+OCR" if ocr_used else ""
    by_page = {}

    def add(page_no, signal):
        by_page.setdefault(page_no, []).append(signal)

    add(1, "PDF_FIRST_PAGE_JACKET_POSITION" + suffix)
    for i, text in enumerate(texts):
        page_no = i + 1
        if PAGE_1_OF.search(text):
            add(page_no, "PAGE_1_OF_MARKER" + suffix)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines:
            first = lines[0].upper()
            if any(k in first for k in TITLE_KEYWORDS):
                add(page_no, "FORM_TITLE_FIRST_LINE" + suffix)
    rows = []
    for page_no in sorted(by_page):
        rows.append({
            "pdf": name, "page": page_no, "pages_total": pages_total,
            "signal": ";".join(by_page[page_no]),
            "confidence": "CANDIDATE", "status": "CANDIDATE",
        })
    return rows


def run_boundaries(target, out_csv, use_ocr=False):
    if os.path.isdir(target):
        pdfs = []
        for dirpath, dirnames, filenames in os.walk(target):
            dirnames.sort()
            for name in sorted(filenames):
                if name.lower().endswith(".pdf"):
                    pdfs.append(os.path.join(dirpath, name))
    else:
        pdfs = [target]
    rows = []
    for pdf in pdfs:
        rows.extend(detect_boundaries(pdf, use_ocr=use_ocr))
    os.makedirs(os.path.dirname(os.path.abspath(out_csv)), exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    use_ocr = "--ocr" in argv
    argv = [a for a in argv if a != "--ocr"]
    if len(argv) != 2:
        print("usage: python -m peaches.boundaries <pdf_or_dir> <out_csv> [--ocr]",
              file=sys.stderr)
        return 2
    rows = run_boundaries(argv[0], argv[1], use_ocr=use_ocr)
    cands = sum(1 for r in rows if r["status"] == "CANDIDATE")
    queued = sum(1 for r in rows if r["status"] == "NEEDS_VISION_QUEUE")
    print("boundaries: %d candidate rows, %d image-only PDFs queued -> %s"
          % (cands, queued, argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
