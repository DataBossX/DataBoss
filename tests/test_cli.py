from __future__ import annotations

from databossx.cli import main


def test_census_accepts_repo_root_after_command(tmp_path, capsys):
    (tmp_path / "docs").mkdir()
    assert main(["census", "--repo-root", str(tmp_path)]) == 0
    assert (tmp_path / "docs" / "INVENTORY_CENSUS.json").exists()
    captured = capsys.readouterr().out
    assert "python_modules" in captured
