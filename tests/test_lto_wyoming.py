"""Tests for the Wyoming abstract-index generator and its project manifest."""

from pathlib import Path

from core.land_title_os.chain_graph import ChainGraph, InstrumentNode
from core.land_title_os.manifest import ProjectManifest
from core.land_title_os.wyoming import (
    INDEX_COLUMNS, AbstractHeader, generate_abstract_index,
    generate_certification_letter, missing_document_exceptions,
    write_abstract_index_csv,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

HEADER = AbstractHeader(county="Campbell", lands="T47N-R75W Section 05: All",
                        date="7/13/2026", posted_thru="6/1/2026",
                        indexed_by="Ryan Gille", project="Abstract 4775 Ryder")


def _graph() -> ChainGraph:
    g = ChainGraph()
    g.add(InstrumentNode("4722", "1916-06-24", ["The United States of America"],
                         ["Louis J. Napier"], kind="United States Patent",
                         book_page="003P-0327",
                         legal_description="S/2 S/2 of 5-47N-75W"))
    g.add(InstrumentNode("153006", "1949-01-20", ["Bessie W. Napier"],
                         ["Shell Oil Company, Incorporated"], kind="Oil and Gas Lease",
                         book_page="0002-0577", legal_description="S/2 of 5-47N-75W, aol"))
    return g


def test_index_matches_verified_section5_format(tmp_path):
    rows = generate_abstract_index(HEADER, _graph())
    assert rows[0] == ["Index County:", "Campbell"]
    assert rows[3] == ["Starting Date:", "Inception"]
    assert rows[6] == ["Project:", "Abstract 4775 Ryder"]
    assert rows[7] == INDEX_COLUMNS
    # entries in recording order, patent first
    assert rows[8][0] == "United States Patent" and rows[8][3] == "4722"
    assert rows[9][0] == "Oil and Gas Lease"
    out = write_abstract_index_csv(rows, tmp_path / "index.csv")
    assert out.read_text(encoding="utf-8").splitlines()[0].startswith("Index County:")


def test_certification_letter_needs_signature_and_lists_exceptions():
    g = _graph()
    # 1916 -> 1949 silence surfaces as a coverage-gap exception
    exceptions = missing_document_exceptions(g)
    assert exceptions and "33-year silence" in exceptions[0]
    letter = generate_certification_letter(HEADER, entry_count=2,
                                           exceptions=exceptions, preparer="DataBossX")
    assert "NOT VALID UNTIL SIGNED" in letter
    assert "subject to the following 1 exception" in letter
    assert "not a title opinion" in letter
    clean = generate_certification_letter(HEADER, 2, [], "DataBossX")
    assert "not a substitute for examiner review" in clean


def test_wyoming_manifest_valid():
    m = ProjectManifest.load(
        REPO_ROOT / "projects" / "WY-CAMPBELL-05-47N-75W" / "manifest.json")
    assert (m.client, m.county, m.section) == ("Penterra", "Campbell", "5")
    assert any("CURSOR_REBUILT" in i["description"] for i in m.open_issues)
    cols = m.templates[0]["columns"]
    assert cols == INDEX_COLUMNS
