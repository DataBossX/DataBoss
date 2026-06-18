"""Tests for the parsing heuristics."""

import parsing


def test_clean_text_collapses_whitespace():
    assert parsing.clean_text("a   b\t\tc  ") == "a b c"
    assert parsing.clean_text(None) == ""


def test_extractor_pulls_document_number():
    out = parsing.extractor_llm("Document # 1234567 filed", "http://x")
    assert out["doc_no"] == "1234567"
    assert out["source_url"] == "http://x"


def test_extractor_detects_oil_and_gas_lease():
    out = parsing.extractor_llm("This OIL & GAS LEASE is between...", "u")
    assert out["instrument"] == "Oil & Gas Lease"


def test_extractor_normalizes_iso_date():
    out = parsing.extractor_llm("Recorded 2021-05-09 in book", "u")
    assert out["recording_date"] == "2021-05-09"


def test_extractor_detects_target_legal():
    out = parsing.extractor_llm("Section 1 T7N R63W of the county", "u")
    assert out["legal_short"] == "Sec 1 T7N R63W"


def test_extractor_returns_defaults_on_empty():
    out = parsing.extractor_llm("nothing useful here", "u")
    assert out["doc_no"] is None
    assert out["grantee"] == []
