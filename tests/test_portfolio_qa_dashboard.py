#!/usr/bin/env python3
"""Rules for the read-only portfolio QA dashboard.

These tests use synthetic package labels only. They prove UNKNOWN stays
UNKNOWN, holds stay separated, and frozen benchmarks are not scheduled
for abstract edits.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.portfolio_qa.dashboard import (
    ALL_COLUMNS,
    CANONICAL_PACKAGES,
    LedgerError,
    build,
    load_ledger,
)
from tools.portfolio_qa.schema import (
    UNKNOWN_TOKEN,
    is_frozen_benchmark,
    prefer_evidence,
    refuse_zero_coercion,
)


def _row(package: str, **overrides):
    row = {key: UNKNOWN_TOKEN for key in ALL_COLUMNS}
    row["package"] = package
    row.update(overrides)
    return row


def _canonical_rows(replacements: dict | None = None):
    rows = [_row(name) for name in CANONICAL_PACKAGES]
    if replacements is None:
        return rows
    for name, fields in replacements.items():
        rows[CANONICAL_PACKAGES.index(name)] = _row(name, **fields)
    return rows


def _ledger(tmp_path: Path, rows=None, meta=None) -> Path:
    payload = {
        "meta": meta
        or {
            "generated_utc": "2026-09-14T22:15Z",
            "drive_live_read": "ACCESS_GAP",
            "abstracts_edited": "none",
            "access_note": "synthetic fixture — Drive unread",
        },
        "rows": rows if rows is not None else _canonical_rows(),
    }
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_unknown_is_never_converted_to_zero():
    assert refuse_zero_coercion(UNKNOWN_TOKEN) == UNKNOWN_TOKEN
    assert refuse_zero_coercion(None) == UNKNOWN_TOKEN
    assert refuse_zero_coercion("") == UNKNOWN_TOKEN
    assert refuse_zero_coercion("437") == "437"


def test_source_outranks_receipt_outranks_model():
    assert prefer_evidence("SOURCE", "RECEIPT") == "SOURCE"
    assert prefer_evidence("RECEIPT", "MODEL") == "RECEIPT"
    assert prefer_evidence("MODEL", "UNKNOWN") == "MODEL"
    assert prefer_evidence("UNKNOWN", "SOURCE") == "SOURCE"


def test_missing_package_fails_closed(tmp_path):
    rows = [_row(name) for name in CANONICAL_PACKAGES if name != "P10"]
    path = _ledger(tmp_path, rows=rows)
    with pytest.raises(LedgerError, match="missing required packages"):
        load_ledger(path)


def test_collapsed_holds_fail_closed(tmp_path):
    path = _ledger(
        tmp_path,
        rows=_canonical_rows(
            {
                "P1": {
                    "source_hold": "same-text-hold",
                    "control_custody_hold": "same-text-hold",
                }
            }
        ),
    )
    with pytest.raises(LedgerError, match="collapsed source hold"):
        build(path, tmp_path / "out")


def test_frozen_benchmark_cannot_schedule_abstract_edit(tmp_path):
    path = _ledger(
        tmp_path,
        rows=_canonical_rows(
            {
                "P15": {
                    "status": "FROZEN_BENCHMARK",
                    "next_unique_action": "edit abstract on frozen winner",
                }
            }
        ),
    )
    with pytest.raises(LedgerError, match="frozen benchmark"):
        build(path, tmp_path / "out")


def test_export_preserves_unknown_and_writes_csv_and_markdown(tmp_path):
    path = _ledger(
        tmp_path,
        rows=_canonical_rows(
            {
                "P15": {
                    "status": "FROZEN_BENCHMARK",
                    "next_unique_action": "Use as format donor only. Do not edit abstracts.",
                    "county_denominator": UNKNOWN_TOKEN,
                    "source_hold": UNKNOWN_TOKEN,
                    "control_custody_hold": "FROZEN — control hold, not a source hold",
                    "evidence_class": "RECEIPT",
                },
                "P11": {
                    "county_denominator": "437 handwritten Vision-measured; 461 remains a superseded derived receipt figure",
                    "status": "QA_HOLD",
                    "source_hold": "TRUE_HOLD census class present",
                    "control_custody_hold": "HOLD_NOT_RELEASED",
                    "evidence_class": "SOURCE_PIXEL",
                },
            }
        ),
    )
    out = tmp_path / "isolated"
    written = build(path, out)

    exported = list(csv.DictReader(written["csv"].open(encoding="utf-8")))
    assert [row["package"] for row in exported] == list(CANONICAL_PACKAGES)
    p1 = next(row for row in exported if row["package"] == "P1")
    assert p1["county_denominator"] == UNKNOWN_TOKEN
    assert p1["county_matched"] == UNKNOWN_TOKEN
    assert p1["missing_faces"] == UNKNOWN_TOKEN
    p15 = next(row for row in exported if row["package"] == "P15")
    assert is_frozen_benchmark(p15["status"])
    assert "0" not in {p1["county_denominator"], p1["federal_pages"]}
    markdown = written["md"].read_text(encoding="utf-8")
    assert "UNKNOWN stays UNKNOWN" in markdown
    assert "Abstracts edited" in markdown
    html = written["html"].read_text(encoding="utf-8")
    assert "UNKNOWN" in html
    assert "FROZEN_BENCHMARK" in html
