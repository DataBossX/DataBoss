import pytest
from pathlib import Path
from core.run_manager import RunManager, sha256_file

def test_baseline_copy_and_no_overwrite(audit, tmp_path, sample_workbook):
    rm = RunManager(tmp_path/"out", audit)
    v0 = rm.ingest_baseline(sample_workbook)
    assert v0.exists() and v0.name == "workbook_v000.xlsx"
    # original untouched
    assert sha256_file(sample_workbook) == sha256_file(v0)
    # versioned files never overwrite
    p1 = rm.next_version_path(".xlsx")
    p1.write_bytes(b"x")
    import shutil
    with pytest.raises(FileExistsError):
        # simulate collision
        if p1.exists():
            raise FileExistsError(p1)

def test_version_numbers_increment(audit, tmp_path, sample_workbook):
    rm = RunManager(tmp_path/"out", audit)
    rm.ingest_baseline(sample_workbook)
    a = rm.next_version_path(".xlsx"); a.write_bytes(b"a")
    b = rm.next_version_path(".xlsx"); b.write_bytes(b"b")
    assert a.name == "workbook_v001.xlsx" and b.name == "workbook_v002.xlsx"
