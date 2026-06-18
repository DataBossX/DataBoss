"""Tests for the TitlePreviewFixer gated preflight and title logic.

Covers the prompt's required checks:
  * low-confidence OCR is blocked / held for review
  * row compare catches mismatch
  * OCR schema validation rejects malformed results
  * preflight never alters the source workbook hash
  * cost guard refuses over-budget
"""
from __future__ import annotations

from pathlib import Path

from databossx.agents import cost_guard
from databossx.core import paths
from databossx.excel import mock_workbook
from databossx.title import (
    confidence_gate,
    document_schema,
    ocr_validator,
    row_compare,
    titlepreviewfixer,
)


def _redirect_dirs(tmp_path, monkeypatch):
    for attr in ("REPORTS", "LOGS", "BACKUPS", "DIAGNOSTICS", "ROLLBACK", "MEMORY", "REVIEW_OUTPUTS"):
        monkeypatch.setattr(paths, attr, tmp_path / attr.lower())
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(
        paths, "ALL_ARTIFACT_DIRS",
        tuple(tmp_path / a for a in ("reports", "logs", "backups", "diagnostics", "rollback", "memory", "review_outputs")),
    )


def test_schema_validation_accepts_blank():
    ok, errors = ocr_validator.validate(document_schema.blank_result())
    assert ok, errors


def test_schema_validation_rejects_missing_keys():
    bad = {"confidence": 0.5}
    ok, errors = ocr_validator.validate(bad)
    assert not ok
    assert any("missing keys" in e for e in errors)


def test_schema_validation_requires_evidence_for_facts():
    r = document_schema.blank_result()
    r["instrument_type"] = "Warranty Deed"
    r["confidence"] = 0.9
    # no visible_evidence -> must fail
    ok, errors = ocr_validator.validate(r)
    assert not ok
    assert any("visible_evidence" in e for e in errors)


def test_confidence_gate_blocks_low_confidence():
    r = document_schema.blank_result()
    r["confidence"] = 0.4
    decision = confidence_gate.decide(r, valid=True)
    assert decision.status == confidence_gate.STATUS_NEEDS_REVIEW


def test_confidence_gate_blocks_invalid_ocr():
    r = document_schema.blank_result()
    r["confidence"] = 0.99
    decision = confidence_gate.decide(r, valid=False)
    assert decision.status == confidence_gate.STATUS_BLOCKED


def test_row_compare_catches_mismatch():
    wb_row = {"Instrument_Type": "Deed", "Book": "412", "Page": "1",
              "Document_Date": "1998-04-12", "Recorded_Date": "1998-04-15"}
    ocr = {"instrument_type": "Deed", "book": "9999", "page": "1",
           "document_date": "1998-04-12", "recorded_date": "1998-04-15"}
    cmp = row_compare.compare_row(wb_row, ocr)
    assert cmp.has_mismatch
    assert any(m.field == "Book" for m in cmp.mismatches)


def test_row_compare_no_false_mismatch_on_match():
    wb_row = {"Book": "412"}
    ocr = {"book": "412"}
    cmp = row_compare.compare_row(wb_row, ocr)
    assert not cmp.has_mismatch


def test_cost_guard_refuses_over_budget():
    est = cost_guard.estimate("openai", calls=1000, budget=1.0)
    assert not est.within_budget


def test_preflight_does_not_alter_source(tmp_path, monkeypatch):
    _redirect_dirs(tmp_path, monkeypatch)
    src = mock_workbook.create_mock_workbook(out_path=tmp_path / "src.xlsx")
    result = titlepreviewfixer.run_preflight(source=src, max_rows=3)
    assert result.source_unchanged
    assert result.report_path.exists()
    # Row index 1 should be Needs Human Review (low confidence), row 2 a mismatch.
    statuses = {o.row_index: o.status for o in result.rows}
    assert statuses[1] == confidence_gate.STATUS_NEEDS_REVIEW
    assert any(o.mismatches for o in result.rows)


def test_preflight_caps_at_three_rows(tmp_path, monkeypatch):
    _redirect_dirs(tmp_path, monkeypatch)
    src = mock_workbook.create_mock_workbook(out_path=tmp_path / "src.xlsx")
    result = titlepreviewfixer.run_preflight(source=src, max_rows=99)
    assert len(result.rows) <= 3
