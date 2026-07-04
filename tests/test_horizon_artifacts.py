"""Tests for net-acre computation and examiner review artifacts."""

import csv
from pathlib import Path

from horizon.artifacts import write_all, write_chain_breaks, write_review_worklist
from horizon.chaining import OGLRecord, RunsheetNote
from horizon.models import ReportModel, TitleRow
from horizon.pipeline import chain_to_report


def test_net_mineral_acres_computed_exactly():
    ogl = [OGLRecord(instrument_number="1", grantor="ROOT", grantee="X",
                     conveyed_interest="1/16", legal_description="NE/4 Sec 31",
                     gross_acres="160")]
    notes = [RunsheetNote(instrument_number="1")]
    build = chain_to_report(ogl, notes)
    # 1/16 of 160 gross = exactly 10 net mineral acres
    assert build.report.rows[0].net_mineral_acres == "10.0000"


def test_net_acres_blank_when_gross_unknown():
    ogl = [OGLRecord(instrument_number="1", grantor="A", grantee="B",
                     conveyed_interest="1/2")]  # no gross acres
    build = chain_to_report(ogl, [RunsheetNote(instrument_number="1")])
    assert build.report.rows[0].net_mineral_acres == ""


def test_net_acres_unparseable_gross_flags_review():
    ogl = [OGLRecord(instrument_number="1", grantor="A", grantee="B",
                     conveyed_interest="1/2", gross_acres="lots")]
    build = chain_to_report(ogl, [RunsheetNote(instrument_number="1")])
    row = build.report.rows[0]
    assert row.net_mineral_acres == ""
    assert "Needs Examiner Review" in row.status


def test_review_worklist_csv(tmp_path):
    report = ReportModel(section="31-12N-24W", rows=[
        TitleRow(grantor="A", grantee="B", instrument_number="1", status="ok"),
        TitleRow(grantor="C", grantee="D", instrument_number="2",
                 status="Needs Examiner Review", remarks="Chain break"),
        TitleRow(grantor="E", grantee="F", instrument_number="3",
                 remarks="ESCALATED: HBP unsupported"),
    ])
    path = tmp_path / "worklist.csv"
    n = write_review_worklist(report, path)
    assert n == 2  # only the two flagged rows
    with path.open() as fh:
        rows = list(csv.DictReader(fh))
    insts = {r["instrument_number"]: r["status"] for r in rows}
    assert insts["2"] == "Needs Examiner Review"
    assert insts["3"] == "ESCALATED"


def test_chain_breaks_and_write_all(tmp_path):
    ogl = [OGLRecord(instrument_number="100", grantor="A", grantee="B",
                     conveyed_interest="1/2")]
    notes = [RunsheetNote(instrument_number="999")]  # orphan
    build = chain_to_report(ogl, notes)
    written = write_all(build, tmp_path)
    names = {n for n, _ in written}
    # artifacts are versioned (_vNNN) like the report
    assert names == {"examiner_review_worklist_v001.csv", "chain_breaks_v001.csv"}
    breaks_path = tmp_path / "chain_breaks_v001.csv"
    assert breaks_path.exists()
    with breaks_path.open() as fh:
        breaks = list(csv.DictReader(fh))
    keys = {b["instrument_number"] for b in breaks}
    assert "100" in keys and "999" in keys  # both sides of the break reported
