"""Regression tests for PR#18 review fixes."""

from fractions import Fraction
from pathlib import Path

import pytest

from horizon.audit import AuditLog
from horizon.chaining import OGLRecord, RunsheetNote, build_cross_reference, reconcile_chain
from horizon.config import HorizonConfig
from horizon.foundation import run_cleanup
from horizon.interest import InterestError, parse_acres, try_parse_acres
from horizon.pipeline import chain_to_report, read_ogl_records
from horizon.validation import Requirements, _is_instrument_number_header, validate_report


# -- gross acres must not parse as a fraction interest ---------------------
def test_parse_acres_rejects_fraction():
    with pytest.raises(InterestError):
        parse_acres("1/2")
    assert try_parse_acres("1/2") is None


def test_parse_acres_accepts_decimal_and_commas():
    assert parse_acres("160") == Fraction(160)
    assert parse_acres("1,280.5") == Fraction(2561, 2)
    assert parse_acres("160 acres") == Fraction(160)


def test_net_acres_fraction_gross_flags_review():
    ogl = [OGLRecord(instrument_number="1", grantor="A", grantee="B",
                     conveyed_interest="1/2", gross_acres="1/2")]
    build = chain_to_report(ogl, [RunsheetNote(instrument_number="1")])
    row = build.report.rows[0]
    assert row.net_mineral_acres == ""            # not computed from a fraction
    assert "Needs Examiner Review" in row.status


# -- duplicate instruments must not overwrite xref -------------------------
def test_duplicate_instruments_tracked():
    ogl = [
        OGLRecord(instrument_number="100", grantor="A", grantee="B", conveyed_interest="1/2"),
        OGLRecord(instrument_number="100", grantor="C", grantee="D", conveyed_interest="1/4"),
    ]
    xref = build_cross_reference(ogl, [RunsheetNote(instrument_number="100")])
    entry = xref["100"]
    assert entry.ogl.grantor == "A"               # first kept
    assert len(entry.duplicate_ogls) == 1         # second retained, not dropped
    assert entry.status == "duplicate_ogl"
    assert not entry.matched


# -- grantor continuity ----------------------------------------------------
def test_grantor_continuity_break_flagged():
    records = [
        OGLRecord(instrument_number="1", grantor="ROOT", grantee="X", conveyed_interest="1/2"),
        # grantor Z is NOT the prior grantee X -> chain-of-title break
        OGLRecord(instrument_number="2", grantor="Z", grantee="Y", conveyed_interest="1/4"),
    ]
    result = reconcile_chain("T", records, starting_interest=Fraction(1))
    assert result.needs_examiner_review
    assert not result.links[1].grantor_continuity
    assert any("chain-of-title break" in r.lower() for r in result.review_reasons)


def test_grantor_continuity_ok_when_matches():
    records = [
        OGLRecord(instrument_number="1", grantor="ROOT", grantee="John A. Smith",
                  conveyed_interest="1/2"),
        OGLRecord(instrument_number="2", grantor="JOHN A SMITH", grantee="Y",
                  conveyed_interest="1/4"),
    ]
    result = reconcile_chain("T", records, starting_interest=Fraction(1))
    assert result.links[1].grantor_continuity  # normalized names match


# -- instrument-number header detection ------------------------------------
@pytest.mark.parametrize("header,expected", [
    ("Instrument Number", True),
    ("Instrument No", True),
    ("Doc No", True),
    ("Document Number", True),
    ("Instrument Type", False),
    ("Instrument Date", False),
    ("Instrument Kind", False),
    ("Grantor", False),
])
def test_instrument_number_header(header, expected):
    assert _is_instrument_number_header(header) is expected


# -- required columns gate -------------------------------------------------
def test_required_columns_gate_warns_unknown():
    from horizon.models import ReportModel, TitleRow
    report = ReportModel(section="X", rows=[TitleRow(grantor="A", grantee="B",
                                                     instrument_number="1")])
    reqs = Requirements(required_columns=["grantor", "some_weird_bespoke_col"])
    vr = validate_report(report, reqs)
    assert any(i.severity == "warn" and "some_weird_bespoke_col" in i.field
               for i in vr.issues)
    assert vr.passed  # warn does not fail the gate


# -- dry-run leaves the tree read-only -------------------------------------
def test_dry_run_does_not_move_duplicates(tmp_path):
    root = tmp_path / "Horizon"
    root.mkdir()
    (root / "a.csv").write_bytes(b"same")
    (root / "b.csv").write_bytes(b"same")
    cfg = HorizonConfig(root=root)
    audit = AuditLog(path=None, echo=False)
    result = run_cleanup(cfg, audit, dry_run=True)
    assert result.duplicate_groups == 1
    assert len(result.quarantined) == 1           # identified...
    # ...but nothing moved: both files still present, no trash dir created
    assert (root / "a.csv").exists() and (root / "b.csv").exists()
    assert not cfg.trash.exists()
    assert not cfg.backups.exists()
