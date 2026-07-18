"""End-to-end test of the DataBossX Command Center on the synthetic golden project.

Proves the whole slice runs, produces every deliverable, and -- crucially --
that the deliberately-flawed golden corpus is caught (RED status, the 7/8
mineral shortfall, the over-conveyance, and both chain breaks), never silently
balanced.
"""

from pathlib import Path

import pytest

from databossx.command_center import run_project
from databossx.demo import build_golden_demo


@pytest.fixture()
def golden(tmp_path) -> Path:
    root = tmp_path / "GOLDEN"
    build_golden_demo(root)
    return root


def test_end_to_end_produces_all_deliverables(golden, tmp_path):
    out = tmp_path / "out"
    result = run_project("golden_demo", root=str(golden), output_dir=str(out))

    assert result.ok  # ran without a hard error
    # Every headline deliverable exists on disk and is non-empty.
    for key in ("excel", "dashboard", "pdf"):
        p = Path(result.deliverables[key])
        assert p.exists() and p.stat().st_size > 0, key
    assert (out / "run_manifest.json").exists()
    assert Path(result.deliverables["excel"]).suffix == ".xlsx"
    assert Path(result.deliverables["pdf"]).read_bytes()[:5] == b"%PDF-"


def test_end_to_end_catches_planted_defects(golden, tmp_path):
    result = run_project("golden_demo", root=str(golden),
                         output_dir=str(tmp_path / "out"))
    # The corpus is deliberately broken -> must be RED, never GREEN.
    assert result.rag == "RED"
    assert result.counts["chain_breaks"] == 2
    assert result.counts["tracts"] == 2

    blob = " ".join(str(d) for d in result.defects).lower()
    # 7/8 mineral shortfall on tract 1.
    assert "not 8/8" in blob
    # Over-conveyance in the chain.
    assert "over-conveyance" in blob or "over_conveyance" in blob or "only held" in blob


def test_excel_has_all_expected_sheets(golden, tmp_path):
    import openpyxl

    result = run_project("golden_demo", root=str(golden),
                         output_dir=str(tmp_path / "out"))
    wb = openpyxl.load_workbook(result.deliverables["excel"])
    for sheet in ("Summary", "Runsheet", "Mineral Ownership",
                  "Division of Interest", "Defects", "Evidence"):
        assert sheet in wb.sheetnames


def test_missing_source_folder_is_plain_language_not_crash(tmp_path):
    result = run_project("horizon", root=str(tmp_path / "does_not_exist"))
    assert result.ok is False
    assert result.rag == "RED"
    assert "not found" in result.message.lower()


def test_unknown_project_is_reported(tmp_path):
    result = run_project("not_a_project")
    assert result.ok is False
    assert "unknown project" in result.message.lower()


def test_reruns_back_up_prior_output(golden, tmp_path):
    out = tmp_path / "out"
    run_project("golden_demo", root=str(golden), output_dir=str(out))
    run_project("golden_demo", root=str(golden), output_dir=str(out))
    backups = list((out / "_backups").glob("*"))
    assert backups, "second run should have backed up the first run's deliverables"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
