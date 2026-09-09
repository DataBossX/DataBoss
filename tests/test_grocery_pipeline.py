#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-end tests for grocery_report_pipeline.

These run the entire pipeline against a SYNTHETIC corpus in a temp dir and
assert that:
  * every mission-spec output file is produced,
  * deterministic extraction captures known parties/dates,
  * validation catches the seeded defects (impossible date, decimal-sum,
    exact duplicate),
  * nothing is fabricated (unfound fields stay blank) and every fact is
    traceable to a source file.

Run:  py -m pytest tests/test_grocery_pipeline.py -v
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import grocery_report_pipeline as grp  # noqa: E402


def _read_csv(path: Path):
    with path.open(encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _run_single_document(tmp_path: Path, filename: str, text: str) -> Path:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / filename).write_text(text, encoding="utf-8")
    output = tmp_path / "output"
    grp.run_pipeline(
        corpus,
        output,
        "test",
        apply_quar=False,
        log=grp.BuildLog(),
    )
    return output


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    base = tmp_path_factory.mktemp("grocery")
    corpus = base / "corpus"
    grp.make_synthetic_corpus(corpus)
    out = base / "output"
    log = grp.BuildLog()
    manifest = grp.run_pipeline(corpus, out, "Grocery_Report", apply_quar=False, log=log)
    return {"out": out, "manifest": manifest}


EXPECTED_OUTPUTS = [
    "file_inventory.csv", "file_inventory.xlsx",
    "duplicate_candidates.csv", "quarantine_plan.csv",
    "source_text_index.csv",
    "document_classification.csv",
    "extracted_facts.csv", "extracted_facts.xlsx",
    "reconciliation_table.xlsx", "chain_summary.xlsx", "conflicts_and_gaps.xlsx",
    "validation_report.xlsx", "review_required.csv",
    "Grocery_Report_DRAFT.md", "Grocery_Report_Executive_Summary.md",
    "Grocery_Report_Curative_List.xlsx", "Grocery_Report_Source_Index.xlsx",
    "status_dashboard.html", "status_dashboard.xlsx",
    "run_manifest.json", "extraction_log.csv",
]


def test_all_outputs_exist(run):
    out = run["out"]
    missing = [f for f in EXPECTED_OUTPUTS if not (out / f).exists()]
    assert not missing, f"Missing outputs: {missing}"
    assert (out / "extracted_text").is_dir()


def test_traceability(run):
    facts = _read_csv(run["out"] / "extracted_facts.csv")
    assert facts, "no facts extracted"
    assert all(f["source_file"] for f in facts), "a fact row lacks a source file"


def test_no_fabrication(run):
    # A doc with no royalty must not have a royalty value invented.
    facts = {f["source_file"]: f for f in _read_csv(run["out"] / "extracted_facts.csv")}
    probate = facts.get("05_probate.txt")
    assert probate is not None
    assert probate["royalty"] == "", "royalty should be blank (not fabricated)"
    assert probate["decimal_interest"] == "", "decimal should be blank (not fabricated)"


def test_party_capture(run):
    facts = {f["source_file"]: f for f in _read_csv(run["out"] / "extracted_facts.csv")}
    deed = facts["01_warranty_deed.txt"]
    assert deed["grantor"] == "John Q. Sample"
    assert deed["grantee"] == "Acme Minerals LLC"
    lease = facts["02_oil_gas_lease.txt"]
    assert lease["lessor"] == "Acme Minerals LLC"
    assert lease["lessee"] == "BigRig Operating Inc"


def test_classification(run):
    rows = {r["rel_path"]: r["categories"] for r in
            _read_csv(run["out"] / "document_classification.csv")}
    assert "oil and gas lease" in rows["02_oil_gas_lease.txt"]
    assert "assignment" in rows["03_assignment.txt"]
    assert "probate" in rows["05_probate.txt"]


def test_exact_duplicate_detected(run):
    dups = _read_csv(run["out"] / "duplicate_candidates.csv")
    exact = [d for d in dups if d["match_type"] == "exact-sha256"]
    assert exact, "exact duplicate not detected"
    assert any("COPY" in d["duplicate"] for d in exact)


def test_impossible_date_flagged(run):
    rr = _read_csv(run["out"] / "review_required.csv")
    assert any(r["rule"] == "impossible-date" and r["severity"] == "red" for r in rr)


def test_decimal_sum_flagged(run):
    rr = _read_csv(run["out"] / "review_required.csv")
    dec = [r for r in rr if r["rule"] == "decimal-sum"]
    assert dec, "decimal-sum discrepancy not flagged"
    assert "0.95" in dec[0]["detail"]  # 0.75 + 0.20 from the two owners


def test_unlabeled_date_is_not_promoted_to_recording_date(tmp_path):
    out = _run_single_document(
        tmp_path,
        "deed.txt",
        "MINERAL DEED\n"
        "Grantor: Example A\n"
        "Grantee: Example B\n"
        "Effective Date: 2024-02-03\n"
        "Instrument No. 2024-1001\n"
        "Legal: Section 1, T1N, R1W\n",
    )

    fact = _read_csv(out / "extracted_facts.csv")[0]
    assert fact["effective_date"] == "2024-02-03"
    assert fact["recording_date"] == ""
    issues = _read_csv(out / "review_required.csv")
    assert any(issue["rule"] == "missing-recording-data" for issue in issues)


def test_short_decimals_parse_when_complete_set_is_proven(tmp_path):
    out = _run_single_document(
        tmp_path,
        "owners.txt",
        "COMPLETE OWNER SET\n"
        "Owner A decimal interest: 0.5\n"
        "Owner B decimal interest: 0.5\n"
        "Legal: Section 1, T1N, R1W\n",
    )

    fact = _read_csv(out / "extracted_facts.csv")[0]
    assert fact["decimal_interest"] == "0.5"
    issues = _read_csv(out / "review_required.csv")
    assert not any(issue["rule"] == "decimal-sum" for issue in issues)
    assert not any(issue["rule"] == "decimal-set-incomplete" for issue in issues)


def test_declared_total_is_not_double_counted_as_an_owner(tmp_path):
    out = _run_single_document(
        tmp_path,
        "owners_with_total.txt",
        "COMPLETE OWNER SET\n"
        "Owner A decimal interest: 0.5\n"
        "Total decimal interest: 0.5\n"
        "Legal: Section 1, T1N, R1W\n",
    )

    issues = _read_csv(out / "review_required.csv")
    decimal_sum = [issue for issue in issues if issue["rule"] == "decimal-sum"]
    assert len(decimal_sum) == 1
    assert "0.5" in decimal_sum[0]["detail"]


def test_declared_total_must_match_owner_components(tmp_path):
    out = _run_single_document(
        tmp_path,
        "owners_with_bad_total.txt",
        "COMPLETE OWNER SET\n"
        "Owner A decimal interest: 0.5\n"
        "Total decimal interest: 1.0\n"
        "Legal: Section 1, T1N, R1W\n",
    )

    issues = _read_csv(out / "review_required.csv")
    assert any(
        issue["rule"] == "decimal-total-mismatch"
        and issue["severity"] == "red"
        for issue in issues
    )


def test_incomplete_owner_set_does_not_assert_sum_to_one(tmp_path):
    out = _run_single_document(
        tmp_path,
        "partial_owner_note.txt",
        "PARTIAL OWNER NOTE\n"
        "Owner A decimal interest: 0.5\n"
        "Legal: Section 1, T1N, R1W\n",
    )

    issues = _read_csv(out / "review_required.csv")
    assert not any(issue["rule"] == "decimal-sum" for issue in issues)
    assert any(issue["rule"] == "decimal-set-incomplete" for issue in issues)


def test_negated_all_owners_phrase_is_not_treated_as_complete(tmp_path):
    out = _run_single_document(
        tmp_path,
        "not_all_owners.txt",
        "NOT ALL OWNERS ARE LISTED\n"
        "Owner A decimal interest: 1.0\n"
        "Legal: Section 1, T1N, R1W\n",
    )

    issues = _read_csv(out / "review_required.csv")
    assert any(issue["rule"] == "decimal-set-incomplete" for issue in issues)


@pytest.mark.parametrize("heading", [
    "NOT A COMPLETE OWNER SET",
    "NOT THE COMPLETE OWNER SET",
    "CANNOT BE CONSIDERED A COMPLETE OWNER SET",
    "ALL OWNERS ARE NOT LISTED",
    "OWNER LIST DOESN'T INCLUDE ALL OWNERS",
])
def test_negated_complete_owner_set_is_not_treated_as_complete(
    tmp_path, heading
):
    out = _run_single_document(
        tmp_path,
        "not_complete.txt",
        f"{heading}\n"
        "Owner A decimal interest: 1.0\n"
        "Legal: Section 1, T1N, R1W\n",
    )

    issues = _read_csv(out / "review_required.csv")
    assert any(issue["rule"] == "decimal-set-incomplete" for issue in issues)


def test_manifest_counts(run):
    m = run["manifest"]
    assert m["counts"]["documents"] == 8  # 7 unique + 1 exact copy
    assert m["counts"]["issues_red"] >= 2


def test_rerunnable_idempotent(run, tmp_path):
    # Running twice into the same dir must not raise and must reproduce outputs.
    corpus = tmp_path / "c"
    grp.make_synthetic_corpus(corpus)
    out = tmp_path / "o"
    log = grp.BuildLog()
    grp.run_pipeline(corpus, out, "Grocery_Report", apply_quar=False, log=log)
    grp.run_pipeline(corpus, out, "Grocery_Report", apply_quar=False, log=log)
    assert (out / "run_manifest.json").exists()
