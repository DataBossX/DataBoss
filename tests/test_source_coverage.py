"""Regression tests for OCR-vs-pixel source coverage."""

from __future__ import annotations

from horizon.source_coverage import (
    NO_REVIEW_HOLD,
    OCR_ONLY_HOLD,
    PIXEL_VERIFIED,
    UNRESOLVED,
    classify_source,
    coverage_summary,
)


def test_ocr_complete_but_pixel_unverified_remains_hold():
    record = {
        "source_identity": "x",
        "disposition": "INCLUDE",
        "ocr_reviewed": True,
        "pixel_reviewed": False,
    }
    assert classify_source(record) == OCR_ONLY_HOLD


def test_ocr_confidence_never_promotes_a_record_to_verified():
    record = {
        "source_identity": "x",
        "disposition": "INCLUDE",
        "ocr_reviewed": True,
        "ocr_confidence": 0.99,
        "pixel_reviewed": False,
    }
    assert classify_source(record) == OCR_ONLY_HOLD


def test_pixel_reviewed_is_verified_regardless_of_ocr():
    record = {
        "source_identity": "x",
        "disposition": "INCLUDE",
        "ocr_reviewed": False,
        "pixel_reviewed": True,
    }
    assert classify_source(record) == PIXEL_VERIFIED


def test_blank_disposition_is_unresolved_not_zero():
    record = {"source_identity": "x", "disposition": "", "pixel_reviewed": True}
    assert classify_source(record) == UNRESOLVED


def test_no_review_at_all_is_hold():
    record = {"source_identity": "x", "disposition": "INCLUDE"}
    assert classify_source(record) == NO_REVIEW_HOLD


def test_summary_keeps_hold_and_unresolved_counts_distinct():
    records = [
        {"source_identity": "a", "disposition": "INCLUDE", "pixel_reviewed": True},
        {"source_identity": "b", "disposition": "INCLUDE", "ocr_reviewed": True},
        {"source_identity": "c", "disposition": ""},
    ]
    summary = coverage_summary(records)
    assert summary.total == 3
    assert summary.pixel_verified == 1
    assert summary.ocr_only_hold == 1
    assert summary.unresolved == 1
    assert summary.hold_count == 1
    assert summary.unresolved_or_hold_count == 2
    assert not summary.fully_pixel_verified


def test_summary_all_pixel_verified():
    records = [
        {"source_identity": "a", "disposition": "INCLUDE", "pixel_reviewed": True},
        {"source_identity": "b", "disposition": "NON_TARGET", "pixel_reviewed": True},
    ]
    summary = coverage_summary(records)
    assert summary.fully_pixel_verified
    assert summary.hold_count == 0
    assert summary.unresolved == 0
    assert summary.pixel_coverage_ratio == 1.0


def test_empty_corpus_is_not_silently_fully_verified():
    summary = coverage_summary([])
    assert summary.total == 0
    assert not summary.fully_pixel_verified
