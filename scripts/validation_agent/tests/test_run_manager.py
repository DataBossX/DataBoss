"""Run manager: immutable baseline, versioning, never overwrites source."""
from pathlib import Path

from core.run_manager import RunManager, sha256_file


def test_creates_run_and_baseline(db, tmp_agent, sample_wb):
    rm = RunManager(db, tmp_agent.outputs_dir)
    before = sha256_file(sample_wb)
    run_id = rm.create_run(sample_wb, mode="dry-run")
    assert run_id.startswith("validation_run_")
    # source untouched
    assert sha256_file(sample_wb) == before
    # v0 baseline exists and is recorded
    v0 = rm.run_folder / "versions" / "workbook_v000.xlsx"
    assert v0.exists()
    assert db.count("workbook_versions", "run_id=?", (run_id,)) == 1
    for sub in ("input", "versions", "sources", "reports", "audit", "logs", "escalations", "exports"):
        assert (rm.run_folder / sub).exists()


def test_versions_increment_and_never_overwrite(db, tmp_agent, sample_wb):
    rm = RunManager(db, tmp_agent.outputs_dir)
    rm.create_run(sample_wb)
    p1 = rm.next_version_path()
    assert p1.name == "workbook_v001.xlsx"
    # simulate producing v001
    p1.write_bytes(Path(sample_wb).read_bytes())
    rm.register_version(p1, "repair")
    p2 = rm.next_version_path()
    assert p2.name == "workbook_v002.xlsx"
    assert rm.latest_version().name == "workbook_v001.xlsx"


def test_two_runs_get_distinct_folders(db, tmp_agent, sample_wb):
    rm1 = RunManager(db, tmp_agent.outputs_dir)
    id1 = rm1.create_run(sample_wb)
    rm2 = RunManager(db, tmp_agent.outputs_dir)
    id2 = rm2.create_run(sample_wb, run_id=id1)  # force a collision on the id
    assert rm1.run_folder != rm2.run_folder
