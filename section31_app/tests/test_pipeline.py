"""End-to-end and unit tests for the Section 31 report machine.

These run in CI on Linux with no Windows drive and no network -- exactly the
local-first, fallback-optional guarantees the app makes. They exercise the full
pipeline against generated sample inputs plus the trickiest unit (legal
normalisation / crosswalk).
"""

from __future__ import annotations

import importlib.util

import pytest

from section31_app.config import Section31Config
from section31_app.legal_match import crosswalk, normalize_legal, push_ogl_onto_records
from section31_app.spend import SpendCapExceeded, SpendTracker

openpyxl_missing = importlib.util.find_spec("openpyxl") is None


# --------------------------------------------------------------------------- #
# Legal-description normalisation & crosswalk
# --------------------------------------------------------------------------- #
def test_normalize_aliquots_survive():
    # The classic bug: uppercase aliquots must not be stripped to bare "4".
    assert normalize_legal("Northeast Quarter (NE/4)") == "NE4"
    assert normalize_legal("NW/4") == "NW4"
    assert normalize_legal("SW/4 of SW/4") == normalize_legal("SW/4 SW/4") == "SW4"
    assert "S2" in normalize_legal("South Half of the Southwest Quarter (S/2 SW/4)")


def test_crosswalk_matches_and_pushes_ogl():
    ogls = [
        {"ogl_number": "OGL-1001", "legal_description": "NE/4"},
        {"ogl_number": "OGL-1002", "legal_description": "NW/4"},
    ]
    matches = crosswalk(["Northwest Quarter", "Northeast Quarter (NE/4)"], ogls)
    by_legal = {m.runsheet_legal: m for m in matches}
    assert by_legal["Northwest Quarter"].ogl_number == "OGL-1002"
    assert by_legal["Northwest Quarter"].matched is True
    assert by_legal["Northeast Quarter (NE/4)"].ogl_number == "OGL-1001"

    records = [{"legal_description": "NW/4", "ogl_number": "", "remarks": ""}]
    pushed = push_ogl_onto_records(records, matches)
    assert pushed == 1
    assert records[0]["ogl_number"] == "OGL-1002"


def test_crosswalk_below_threshold_not_matched():
    ogls = [{"ogl_number": "OGL-9", "legal_description": "NE/4"}]
    matches = crosswalk(["South Half of the Southwest Quarter"], ogls)
    assert matches[0].matched is False


# --------------------------------------------------------------------------- #
# Spend cap
# --------------------------------------------------------------------------- #
def test_spend_cap_hard_stops():
    tracker = SpendTracker(cap=100.0)
    tracker.record("img a", 60)
    assert tracker.remaining == 40.0
    assert tracker.can_spend(40) is True
    assert tracker.can_spend(41) is False
    with pytest.raises(SpendCapExceeded):
        tracker.record("img b", 50)
    assert tracker.total == 60.0  # rejected purchase was not counted


# --------------------------------------------------------------------------- #
# Full pipeline (needs openpyxl)
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(openpyxl_missing, reason="openpyxl not installed")
def test_full_pipeline_end_to_end(tmp_path):
    from section31_app.pipeline import run_pipeline
    from section31_app.tests.make_sample_inputs import main as make_inputs

    root = tmp_path / "Roger Mills"
    root.mkdir()
    make_inputs(str(root))

    result = run_pipeline(Section31Config.from_env(str(root)))

    # The product exists and stands alone in the main folder.
    assert (root / result["final_workbook"].split("/")[-1]).exists()
    assert result["clean"] is True

    # Data actually flowed through the machine.
    assert result["ownership_totals"]["owners"] >= 3
    assert result["ownership_totals"]["total_net_mineral_acres"] > 0
    assert result["crosswalk_matched"] >= 2
    assert result["ogl_pushed"] >= 1
    assert result["wells"] >= 1

    # Spend cap respected; no QA errors escaped.
    assert result["spend"]["spent_usd"] <= result["spend"]["cap_usd"]
    assert "NOT READY" not in result["verdict"]


@pytest.mark.skipif(openpyxl_missing, reason="openpyxl not installed")
def test_pipeline_empty_root_seeds_template(tmp_path):
    from section31_app.pipeline import run_pipeline

    root = tmp_path / "empty"
    result = run_pipeline(Section31Config.from_env(str(root)))
    assert (root / "SECTION31_12N_24W_ROGER_MILLS_FINAL_OWNERSHIP_TITLE_REPORT.xlsx").exists()
    assert result["ownership_totals"]["owners"] == 0
