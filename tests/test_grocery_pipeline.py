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
    # 7 text docs + 1 ownership CSV + 1 exact copy
    assert m["counts"]["documents"] == 9
    assert m["counts"]["issues_red"] >= 2
    assert m["counts"]["tracts"] == 2  # Section 12 and Section 8, canonicalized


def test_rowwise_ownership_extraction(run):
    """The ownership CSV must yield one traceable fact per owner row."""
    facts = _read_csv(run["out"] / "extracted_facts.csv")
    owners = [f for f in facts if f["source_file"] == "08_ownership_schedule.csv"]
    assert len(owners) == 3, "expected one fact per owner row"
    names = {f["owner"] for f in owners}
    assert names == {"Alpha Family Trust", "Beta Holdings LLC", "Gamma Resources LP"}
    for f in owners:
        assert "row:" in f["source_page"], "row-level source anchor missing"
        assert f["decimal_interest"], "decimal not captured from column"


def test_clean_tract_not_flagged(run):
    """Section 8 owners sum to exactly 1.0 -> must NOT raise a decimal-sum flag."""
    rr = _read_csv(run["out"] / "review_required.csv")
    dec = [r for r in rr if r["rule"] == "decimal-sum"]
    subjects = {r["subject"] for r in dec}
    assert not any("SEC 8-" in s for s in subjects), "clean tract wrongly flagged"
    assert any("SEC 12-" in s for s in subjects), "dirty tract not flagged"


def test_canonical_tract_key():
    a = grp.canonical_tract("Section 12, T7N, R63W")
    b = grp.canonical_tract("Sec 12 T7N R63W")
    c = grp.canonical_tract("Section 12, Township 7 North, Range 63 West")
    assert a == b == c == "SEC 12-T7N-R63W"


def test_aliquot_tracts_kept_separate():
    """NE/4 and SW/4 of the same section must NOT collapse to one tract."""
    ne = grp.canonical_tract("NE/4 Section 1, T1N, R1W")
    sw = grp.canonical_tract("SW/4 Section 1, T1N, R1W")
    assert ne != sw
    assert "SEC 1-T1N-R1W" in ne and "SEC 1-T1N-R1W" in sw
    assert "NE/4" in ne and "SW/4" in sw


def test_percentage_decimals_scaled():
    """Percent-form interests must be scaled by 100 for summation."""
    assert grp._to_float("25%") == 0.25
    assert grp._to_float("100%") == 1.0
    assert grp._to_float("0.25") == 0.25
    assert grp._to_float("78.5%") == 0.785
    assert grp._to_float("") is None


def test_header_synonym_wholeword():
    """Short synonyms must not match inside unrelated header text."""
    m = grp._map_header(["Filename", "Owner Name", "Decimal Interest"])
    # 'name' must not steal 'Filename'; 'Owner Name' -> owner; decimal -> decimal.
    assert m.get(1) == "owner"
    assert m.get(2) == "decimal_interest"
    assert 0 not in m  # 'Filename' maps to nothing


def test_percentage_ownership_sheet_not_flagged(tmp_path):
    """A CSV whose decimals are percentages summing to 100% must reconcile to 1.0."""
    corpus = tmp_path / "c"
    corpus.mkdir()
    (corpus / "own_pct.csv").write_text(
        "Mineral Owner,Legal Description,Decimal Interest\n"
        "A,\"Section 5, T1N, R1W\",25%\n"
        "B,\"Section 5, T1N, R1W\",25%\n"
        "C,\"Section 5, T1N, R1W\",50%\n", encoding="utf-8")
    out = tmp_path / "o"
    grp.run_pipeline(corpus, out, "Grocery_Report", apply_quar=False, log=grp.BuildLog())
    rr = _read_csv(out / "review_required.csv")
    assert not any(r["rule"] == "decimal-sum" for r in rr), \
        "percentage decimals summing to 100% wrongly flagged"


def test_rerunnable_idempotent(run, tmp_path):
    # Running twice into the same dir must not raise and must reproduce outputs.
    corpus = tmp_path / "c"
    grp.make_synthetic_corpus(corpus)
    out = tmp_path / "o"
    log = grp.BuildLog()
    grp.run_pipeline(corpus, out, "Grocery_Report", apply_quar=False, log=log)
    grp.run_pipeline(corpus, out, "Grocery_Report", apply_quar=False, log=log)
    assert (out / "run_manifest.json").exists()
