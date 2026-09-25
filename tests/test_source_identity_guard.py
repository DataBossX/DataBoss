"""Regression tests for source-identity retention."""

from horizon.source_identity_guard import source_identity_guard


def _source(identity, disposition="UNRESOLVED"):
    return {"source_identity": identity, "disposition": disposition}


def test_passes_unchanged_source_universe():
    previous = [_source("a", "INCLUDE"), _source("b", "NON_TARGET"), _source("c")]
    current = [_source("a", "INCLUDE"), _source("b", "NON_TARGET"), _source("c", "SUPPORT_CONTINUATION")]
    report = source_identity_guard(previous, current, expected_count=3)
    assert report.passed
    assert report.missing_identities == []


def test_fails_when_cleanup_drops_source():
    previous = [_source("a"), _source("b"), _source("c")]
    current = [_source("a"), _source("c")]
    report = source_identity_guard(previous, current, expected_count=3)
    assert not report.passed
    assert report.missing_identities == ["b"]
    assert report.current_count == 2


def test_fails_on_duplicate_or_missing_disposition():
    previous = [_source("a"), _source("b")]
    current = [_source("a"), _source("a"), {"source_identity": "b", "disposition": ""}]
    report = source_identity_guard(previous, current)
    assert not report.passed
    assert report.duplicate_identities == ["a"]
    assert report.missing_dispositions == ["b"]


def test_allows_new_source_from_newer_verified_census():
    previous = [_source("a"), _source("b")]
    current = [_source("a"), _source("b"), _source("c")]
    report = source_identity_guard(previous, current, expected_count=3)
    assert report.passed
