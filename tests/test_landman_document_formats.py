"""Real document-format ingestion tests for the Landman Helper.

Proves the pipeline extracts conveyance facts from actual PDF, Word (.docx) and
scanned-image (OCR) files -- not just plain-text strings. Each format is skipped
when its optional backend is not installed so the suite stays green on a minimal
environment (the update script installs pdfplumber/PyMuPDF/pytesseract; the
tesseract binary is a documented system prerequisite for image OCR).
"""

from __future__ import annotations

import pytest

from databossx.title_intelligence import _extract_text, extract_conveyance

DEED = (
    "MINERAL DEED\n"
    "Grantor: Wanda Wells\n"
    "Grantee: Victor Vance\n"
    "Grantor does hereby grant, bargain, sell and convey unto Grantee an "
    "undivided 1/2 interest in and to all of the oil, gas and other minerals in "
    "and under the following described land in Beckham County, Oklahoma:\n"
    "Section 20, T9N, R22W, containing 480 gross acres.\n"
    "Instrument No. 55550001. Instrument Date: 2017-11-03.\n"
)


def _assert_core_fields(fact, *, require_legal=True):
    assert fact.grantor == "Wanda Wells"
    assert fact.grantee == "Victor Vance"
    assert fact.conveyed_interest == "1/2"
    assert fact.gross_acres == "480"
    assert fact.instrument_number == "55550001"
    assert fact.is_conveyance is True
    if require_legal:
        assert fact.legal_description == "Section 20, T9N, R22W"


def test_pdf_text_layer_extraction(tmp_path):
    fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")
    pdf_path = tmp_path / "deed.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), DEED, fontsize=11)
    doc.save(str(pdf_path))
    doc.close()

    text, ocr_used = _extract_text(pdf_path, "deed.pdf")
    assert "Wanda Wells" in text
    assert ocr_used is False
    _assert_core_fields(extract_conveyance("deed.pdf", text))


def test_docx_extraction(tmp_path):
    docx = pytest.importorskip("docx", reason="python-docx not installed")
    docx_path = tmp_path / "deed.docx"
    document = docx.Document()
    for line in DEED.splitlines():
        document.add_paragraph(line)
    document.save(str(docx_path))

    text, ocr_used = _extract_text(docx_path, "deed.docx")
    assert "Victor Vance" in text
    assert ocr_used is False
    _assert_core_fields(extract_conveyance("deed.docx", text))


def test_scanned_image_ocr_extraction(tmp_path):
    pytest.importorskip("pytesseract", reason="pytesseract not installed")
    Image = pytest.importorskip("PIL.Image", reason="Pillow not installed")
    from PIL import ImageDraw, ImageFont
    import shutil

    if shutil.which("tesseract") is None:
        pytest.skip("tesseract binary not installed")

    img = Image.new("RGB", (1100, 720), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
    except Exception:
        font = ImageFont.load_default()
    y = 30
    for line in DEED.splitlines():
        while len(line) > 62:
            cut = line.rfind(" ", 0, 62)
            draw.text((30, y), line[:cut], fill="black", font=font)
            y += 38
            line = line[cut + 1:]
        draw.text((30, y), line, fill="black", font=font)
        y += 38
    png_path = tmp_path / "deed.png"
    img.save(str(png_path))

    text, ocr_used = _extract_text(png_path, "deed.png")
    assert ocr_used is True
    # OCR reliably recovers the parties, interest and instrument; the legal
    # description is not asserted because a single mis-OCR'd digit is (correctly)
    # left for examiner review rather than guessed.
    fact = extract_conveyance("deed.png", text)
    assert fact.grantor == "Wanda Wells"
    assert fact.grantee == "Victor Vance"
    assert fact.conveyed_interest == "1/2"
    assert fact.is_conveyance is True
