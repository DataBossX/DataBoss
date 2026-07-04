"""Regression tests for the Roger Mills title report builder (codexv1).

Covers the interest chain-out and the review-hardening fixes. Kept in the same
directory as the tool so `import roger_mills_title_report_builder` resolves under
pytest's default import mode.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

pytest.importorskip("openpyxl")

import roger_mills_title_report_builder as rm  # noqa: E402


# -- interest parsing -------------------------------------------------------
def test_parse_interest_fraction():
    assert rm.parse_interest_fraction("1/2") == Fraction(1, 2)
    assert rm.parse_interest_fraction("0.25") == Fraction(1, 4)
    assert rm.parse_interest_fraction("12.5%") == Fraction(1, 8)
    assert rm.parse_interest_fraction("1/8 RI") == Fraction(1, 8)
    assert rm.parse_interest_fraction("640") is None      # >1, not a fraction
    assert rm.parse_interest_fraction("") is None
    assert rm.parse_interest_fraction("n/a") is None


# -- chain-out --------------------------------------------------------------
def _row(grantor, grantee, interest, acreage="640"):
    return rm.TitleRow({"grantor": grantor, "grantee": grantee,
                        "interest": interest, "acreage": acreage}, "s", 1)


def test_chain_out_reconciles():
    chain = rm.chain_out_interest([
        _row("US PATENT", "ALICE", "1"),
        _row("ALICE", "BOB", "1/2"),
        _row("BOB", "CAROL", "1/2"),
    ])
    assert chain["ownership"]["ALICE"] == Fraction(1, 2)
    assert chain["ownership"]["CAROL"] == Fraction(1, 2)
    assert chain["reconciles"] and chain["gap_count"] == 0
    assert chain["gross_acres"] == 640.0


def test_chain_out_flags_vesting_gap():
    chain = rm.chain_out_interest([
        _row("US PATENT", "ALICE", "1"),
        _row("ZED", "EVE", "1/2"),   # ZED never vested
    ])
    assert chain["gap_count"] == 1
    assert not chain["reconciles"]
    assert any("not previously vested" in w for w in chain["warnings"])


def test_chain_out_self_conveyance_and_blank_grantee():
    chain = rm.chain_out_interest([
        _row("US PATENT", "ALICE", "1"),
        _row("ALICE", "ALICE", "1/2"),   # correction
        _row("ALICE", "", "1/4"),        # blank grantee
    ])
    assert chain["ownership"].get("ALICE") == Fraction(1)
    assert "" not in chain["ownership"]
    assert len(chain["warnings"]) == 2


# -- review-hardening fixes -------------------------------------------------
def test_header_matching_rejects_short_token_substrings():
    assert rm.match_header("Notes") == "remarks"     # not entry_no via "no"
    assert rm.match_header("Total") is None           # not grantee via "to"
    assert rm.match_header("Grantor") == "grantor"
    assert rm.match_header("Book No") == "book"
    assert rm.match_header("Recording Date") == "recorded_date"


def test_norm_text_integral_float_has_no_decimal():
    # A doc number read as 456.0 must dedup-key identically to "456".
    assert rm.norm_text(456.0) == "456"
    assert rm.norm_doc_ref(456.0) == "456"


def test_norm_date_does_not_fabricate():
    # A page/reference number is not a date; a messy non-date cell is not a date.
    assert rm.norm_date("12345") is None            # out of serial range
    assert rm.norm_date("Section 31 twp 12N") is None
    # A real date still parses.
    assert rm.norm_date("1975-06-01") is not None


def test_norm_date_recovers_annotated_dates():
    # Real dates embedded in annotated cells are recovered (no fuzzy fabrication).
    assert rm.norm_date("1/2/1990 re-recorded") is not None
    assert rm.norm_date("June 5, 1975 filed") is not None


def test_header_abbreviations_with_punctuation_map():
    assert rm.match_header("No.") == "entry_no"
    assert rm.match_header("Pg.") == "page"
    assert rm.match_header("Bk.") == "book"


def test_name_match_tolerates_variance_but_not_distinct():
    assert rm._name_match("ALICE J JONES", "ALICE JONES") is True
    assert rm._name_match("ALICE", "ALICE JONES") is False
    assert rm._name_match("BOB SMITH", "BOB JONES") is False


def test_ogl_header_and_register():
    assert rm.match_header("OGL") == "ogl"
    assert rm.match_header("Lease Number") == "ogl"
    reg = rm.collect_ogl_register([
        rm.TitleRow({"ogl": "OGL-5001", "grantor": "ALICE", "grantee": "OP X",
                     "book": "200", "page": "10", "interest": "1/8"}, "s", 1),
        rm.TitleRow({"ogl": "OGL-5001", "grantor": "ALICE", "grantee": "OP X"}, "s", 2),
        rm.TitleRow({"ogl": "OGL-5002", "grantor": "BOB", "grantee": "OP Y"}, "s", 3),
    ])
    assert [o["ogl"] for o in reg] == ["OGL-5001", "OGL-5002"]  # deduped


def test_lease_rows_excluded_from_mineral_chain():
    chain = rm.chain_out_interest([
        rm.TitleRow({"grantor": "US PATENT", "grantee": "ALICE", "book": "1",
                     "page": "1", "interest": "1", "acreage": "640"}, "s", 1),
        rm.TitleRow({"grantor": "ALICE", "grantee": "BOB", "book": "2", "page": "2",
                     "interest": "1/2", "acreage": "640"}, "s", 2),
        # a lease must NOT reduce fee-mineral ownership:
        rm.TitleRow({"grantor": "ALICE", "grantee": "OPERATOR",
                     "ogl": "OGL-1", "interest": "1/8",
                     "doc_type": "Oil and Gas Lease"}, "s", 3),
    ])
    assert "OPERATOR" not in chain["ownership"]
    assert chain["ownership"].get("ALICE") == Fraction(1, 2)
    assert chain["ownership"].get("BOB") == Fraction(1, 2)


def test_is_title_sheet():
    def sa(header_map):
        return rm.SheetAnalysis(name="s", max_row=5, max_col=5, header_row=1,
                                header_map=header_map, data_rows=4, filled_cells=10,
                                formula_cells=0, blank_ratio=0.5)
    assert rm._is_title_sheet(sa({1: "grantor", 2: "grantee"}))     # chain sheet
    assert rm._is_title_sheet(sa({1: "ogl", 2: "interest"}))         # OGL sheet
    # Book/Page ALONE (no parties, no OGL) is a tract-style sheet -> not a chain
    # source; we don't "go off the tract sheets".
    assert not rm._is_title_sheet(sa({1: "book", 2: "page"}))
    assert not rm._is_title_sheet(sa({1: "legal_description", 2: "acreage"}))


def test_load_dotenv(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('OKCOUNTY_API_KEY="abc123"\n# comment\nFOO=bar\n', encoding="utf-8")
    monkeypatch.delenv("OKCOUNTY_API_KEY", raising=False)
    monkeypatch.delenv("FOO", raising=False)
    n = rm.load_dotenv(env)
    import os
    assert n == 2
    assert os.environ["OKCOUNTY_API_KEY"] == "abc123"
    assert os.environ["FOO"] == "bar"


def test_load_dotenv_bom_and_export(tmp_path, monkeypatch):
    import os
    env = tmp_path / ".env"
    # BOM + a shell-style 'export' prefix -- both must yield the clean key name.
    env.write_bytes("﻿KEYA=1\nexport KEYB=2\n".encode("utf-8"))
    for k in ("KEYA", "KEYB"):
        monkeypatch.delenv(k, raising=False)
    rm.load_dotenv(env)
    assert os.environ.get("KEYA") == "1"      # not "﻿KEYA"
    assert os.environ.get("KEYB") == "2"      # not "export KEYB"


def test_release_not_treated_as_lease():
    # "Release of Lien" contains "lease" but must remain in the mineral chain.
    chain = rm.chain_out_interest([
        rm.TitleRow({"grantor": "US PATENT", "grantee": "ALICE", "book": "1",
                     "page": "1", "interest": "1", "doc_type": "Patent"}, "s", 1),
        rm.TitleRow({"grantor": "ALICE", "grantee": "BOB", "book": "2", "page": "2",
                     "interest": "1/2", "doc_type": "Release of Lien"}, "s", 2),
    ])
    assert chain["ownership"].get("BOB") == Fraction(1, 2)  # not dropped


def test_report_quality_score():
    merged = [
        rm.TitleRow({"grantor": "US PATENT", "grantee": "ALICE", "book": "1",
                     "page": "1", "interest": "1", "doc_type": "Patent",
                     "acreage": "640"}, "s", 1),
        rm.TitleRow({"grantor": "ALICE", "grantee": "BOB", "book": "2", "page": "2",
                     "interest": "1/2", "doc_type": "WD", "acreage": "640"}, "s", 2),
    ]
    chain = rm.chain_out_interest(merged)
    score, lines = rm.score_report_quality(merged, chain, [], {}, [])
    assert 0 <= score <= 100
    assert any("REPORT QUALITY SCORE" in ln for ln in lines)
    # Fully-sourced, reconciling chain, but unverified -> verification is the lever.
    assert any("improvement lever" in ln for ln in lines)
    # Empty input scores zero, doesn't crash.
    assert rm.score_report_quality([], chain, [], {}, [])[0] == 0.0


def test_chain_out_reconciles_name_variance():
    chain = rm.chain_out_interest([
        _row("US PATENT", "ALICE JONES", "1"),
        _row("ALICE J JONES", "BOB SMITH", "1/2"),   # variance -> reconcile
        _row("BOB SMITH", "CAROL", "1/4"),
        _row("DAVE", "EVE", "1/8"),                  # genuine gap
        _row("CAROL", "FRANK", "1/4"),
    ])
    assert chain["gap_count"] == 1                    # only DAVE
    assert chain["name_notes"]
    assert chain["ownership"].get("ALICE JONES") == Fraction(1, 2)
