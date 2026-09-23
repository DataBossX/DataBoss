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


# ===========================================================================
# Regression tests -- issue #94 item 2: recording_date must never be
# fabricated from an unrelated/unlabeled date.
# ===========================================================================
def _run_custom_corpus(tmp_path, docs: dict):
    """Build a small synthetic corpus with the given {filename: text} and
    run the full pipeline against it, in isolation from the shared `run`
    fixture's corpus."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    for name, body in docs.items():
        (corpus / name).write_text(body, encoding="utf-8")
    out = tmp_path / "output"
    log = grp.BuildLog()
    manifest = grp.run_pipeline(corpus, out, "Test_Report", apply_quar=False, log=log)
    return out, manifest


def test_recording_date_blank_without_label_and_review_required(tmp_path):
    # MANDATORY REGRESSION (issue #94 item 2): a document with an
    # effective/execution date but NO recording label must yield a blank
    # recording_date plus a REVIEW REQUIRED flag.
    docs = {
        "a_no_recording_label.txt": (
            "SYNTHETIC TEST DOCUMENT -- NOT REAL TITLE DATA\n"
            "MINERAL DEED\n"
            "Grantor: Alpha Owner\n"
            "Grantee: Beta Buyer\n"
            "Effective Date: 2015-04-10  Executed: 2015-04-10\n"
            "Legal: Section 4, T2N, R55W\n"
        ),
    }
    out, _ = _run_custom_corpus(tmp_path, docs)
    facts = {f["source_file"]: f for f in _read_csv(out / "extracted_facts.csv")}
    fact = facts["a_no_recording_label.txt"]
    assert fact["execution_date"] == "2015-04-10"
    assert fact["effective_date"] == "2015-04-10"
    assert fact["recording_date"] == "", (
        "recording_date must stay blank when no recorded/recording-date/filed "
        "label is present -- it must never be fabricated from an unrelated date "
        "(here, the effective/execution date)")
    rr = _read_csv(out / "review_required.csv")
    assert any(r["rule"] == "missing-recording-data" and r["subject"] == "a_no_recording_label.txt"
               for r in rr), (
        "missing recording data must be flagged REVIEW REQUIRED, not silently "
        "suppressed by a fabricated recording_date")


def test_unlabeled_date_kept_separate_not_used_as_recording_date(tmp_path):
    # A stray, unrelated date with no recording/effective/execution label
    # nearby must surface as a candidate under `unlabeled_dates`, never as
    # `recording_date`.
    docs = {
        "b_stray_date.txt": (
            "SYNTHETIC TEST DOCUMENT -- NOT REAL TITLE DATA\n"
            "CORRESPONDENCE regarding title matter.\n"
            "Please respond by 2022-11-01.\n"
            "Legal: Section 4, T2N, R55W\n"
        ),
    }
    out, _ = _run_custom_corpus(tmp_path, docs)
    facts = {f["source_file"]: f for f in _read_csv(out / "extracted_facts.csv")}
    fact = facts["b_stray_date.txt"]
    assert fact["recording_date"] == "", "unlabeled date must not become recording_date"
    assert "2022-11-01" in fact["unlabeled_dates"], (
        "the unlabeled date should still be surfaced as a candidate for human review")


def test_recording_date_still_captured_when_labeled(tmp_path):
    # Regression: labeled recording dates must keep working exactly as before.
    docs = {
        "c_recorded.txt": (
            "SYNTHETIC TEST DOCUMENT -- NOT REAL TITLE DATA\n"
            "MINERAL DEED\n"
            "Grantor: Alpha Owner\n"
            "Grantee: Beta Buyer\n"
            "Effective Date: 2015-04-10\n"
            "Recorded: 2015-04-20  Book 9 Page 4\n"
            "Legal: Section 4, T2N, R55W\n"
        ),
    }
    out, _ = _run_custom_corpus(tmp_path, docs)
    facts = {f["source_file"]: f for f in _read_csv(out / "extracted_facts.csv")}
    fact = facts["c_recorded.txt"]
    assert fact["recording_date"] == "2015-04-20"


# ===========================================================================
# Regression tests -- issue #94 item 3: _DECIMAL_RX digit-count restriction,
# and sum-to-one only asserted for a proven-complete owner set.
# ===========================================================================
def _make_fact(source_file, values, all_decimals=None):
    f = grp.Fact(source_file=source_file)
    f.values.update(values)
    f.all_decimals = all_decimals or []
    return f


def test_decimal_regex_accepts_short_precision():
    # MANDATORY REGRESSION (issue #94 item 3): ordinary values like 0.5 /
    # 0.25 / 0.125 must parse (previously required 4-9 digits after '.').
    assert grp._DECIMAL_RX.findall("decimal interest 0.5") == ["0.5"]
    assert grp._DECIMAL_RX.findall("decimal interest of 0.25") == ["0.25"]
    assert grp._DECIMAL_RX.findall("decimal: 0.125") == ["0.125"]
    # still anchored to the "decimal interest" label context -- an unrelated
    # 0.5 in prose must not match.
    assert grp._DECIMAL_RX.findall("the tract is roughly 0.5 miles wide") == []


def test_decimal_05_plus_05_reconciles_to_one(tmp_path):
    # MANDATORY REGRESSION: 0.5 + 0.5 parses and reconciles to 1.0 (complete
    # owner set: both decimals come from one self-contained ownership doc).
    legal = "Section 8, T3N, R58W"
    f = _make_fact("single_ownership_sheet.txt", {"legal_description": legal},
                    all_decimals=[0.5, 0.5])
    out = tmp_path / "out_complete"
    log = grp.BuildLog()
    recon = grp.reconcile([f], out, log)
    assert not any(c[0] == "decimal-sum" for c in recon["conflicts"]), (
        "0.5 + 0.5 from a single complete ownership document must reconcile "
        "to 1.0 without a false decimal-sum conflict")


def test_decimal_sum_not_asserted_for_incomplete_owner_set(tmp_path):
    # MANDATORY REGRESSION: an incomplete owner set (decimals scattered
    # across unrelated documents) must NOT assert a false sum-to-one
    # conflict, even though 0.6 + 0.9 = 1.5 != 1.0.
    legal = "Section 9, T3N, R58W"
    f1 = _make_fact("assignment_partial.txt", {"legal_description": legal}, all_decimals=[0.6])
    f2 = _make_fact("ownership_sheet_other.txt", {"legal_description": legal}, all_decimals=[0.9])
    out = tmp_path / "out_incomplete"
    log = grp.BuildLog()
    recon = grp.reconcile([f1, f2], out, log)
    assert not any(c[0] == "decimal-sum" for c in recon["conflicts"]), (
        "decimals spread across multiple unrelated documents are not proof of "
        "a complete owner set and must not raise a false decimal-sum conflict")


def test_decimal_sum_conflict_still_flagged_when_owner_set_complete(tmp_path):
    # A genuine imbalance within a single, complete ownership document must
    # still be flagged (this is what test_decimal_sum_flagged also covers
    # end-to-end via the synthetic corpus).
    legal = "Section 10, T3N, R58W"
    f = _make_fact("single_sheet_incomplete_sum.txt", {"legal_description": legal},
                    all_decimals=[0.6, 0.3])
    out = tmp_path / "out_genuine_conflict"
    log = grp.BuildLog()
    recon = grp.reconcile([f], out, log)
    dec_conflicts = [c for c in recon["conflicts"] if c[0] == "decimal-sum"]
    assert dec_conflicts, "a genuine imbalance within a complete owner set must still be flagged"
    assert "0.9" in dec_conflicts[0][2]
