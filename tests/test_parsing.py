"""Tests for automation/parsing.py heuristics (needs tenacity)."""
import importlib

import pytest

pytest.importorskip("tenacity")
parsing = importlib.import_module("automation.parsing")


def test_clean_text_collapses_whitespace():
    assert parsing.clean_text("a   b\t c") == "a b c"
    assert parsing.clean_text(None) == ""
    assert parsing.clean_text("  padded  ") == "padded"


def test_extractor_pulls_document_number():
    out = parsing.extractor_llm("Document # 1234567 filed", "http://x")
    assert out["doc_no"] == "1234567"
    assert out["source_url"] == "http://x"


def test_extractor_detects_oil_and_gas_lease():
    out = parsing.extractor_llm("This OIL & GAS LEASE ...", "u")
    assert out["instrument"] == "Oil & Gas Lease"


def test_extractor_normalizes_dates():
    assert parsing.extractor_llm("recorded 01/02/2021", "u")["recording_date"] == "01-02-2021"
    assert parsing.extractor_llm("on 2021-05-06", "u")["recording_date"] == "2021-05-06"


def test_extractor_detects_target_legal():
    out = parsing.extractor_llm("Section 1, T7N, R63W tract", "u")
    assert out["legal_short"] == "Sec 1 T7N R63W"


def test_extractor_returns_full_shape():
    out = parsing.extractor_llm("nothing useful", "u")
    for key in ("doc_no", "instrument", "recording_date", "grantor",
                "grantee", "legal_short", "addresses", "source_url"):
        assert key in out
