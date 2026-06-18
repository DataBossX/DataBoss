"""Unit tests for the OCR/text-extraction layer."""

import pytest

import ocr


def test_text_file_decodes_directly():
    result = ocr.extract_text(b"Hello world", "note.txt", "text/plain")
    assert result["raw_text"] == "Hello world"
    assert result["cleaned_text"] == "Hello world"
    assert result["confidence_score"] == 1.0
    assert result["ocr_engine"] == "text-decode"
    assert result["processing_time"] >= 0


def test_text_by_content_type_without_extension():
    result = ocr.extract_text(b"a,b,c", "data", "text/csv")
    assert result["ocr_engine"] == "text-decode"


def test_invalid_utf8_is_replaced_not_raised():
    result = ocr.extract_text(b"\xff\xfe bad bytes", "x.txt", "text/plain")
    assert "bad bytes" in result["raw_text"]  # decoded with errors="replace"


def test_unsupported_type_raises():
    with pytest.raises(ocr.OCRError):
        ocr.extract_text(b"MZ\x90", "evil.exe", "application/x-msdownload")


@pytest.mark.parametrize(
    "name,ct,expected",
    [
        ("a.txt", None, True),
        ("a.csv", None, True),
        ("a", "application/json", True),
        ("a.png", None, False),
        ("a", "image/png", False),
    ],
)
def test_is_text(name, ct, expected):
    assert ocr.is_text(name, ct) is expected


@pytest.mark.parametrize(
    "name,ct,expected",
    [
        ("a.png", None, True),
        ("a", "image/jpeg", True),
        ("a.txt", None, False),
    ],
)
def test_is_image(name, ct, expected):
    assert ocr.is_image(name, ct) is expected


def test_image_ocr_without_tesseract_raises_clear_error():
    # tesseract is not installed in CI; the error must be explicit, not a fake result.
    if ocr.tesseract_available():
        pytest.skip("tesseract is installed; negative path not applicable")
    with pytest.raises(ocr.OCRError):
        ocr.extract_text(b"\x89PNG\r\n", "scan.png", "image/png")
