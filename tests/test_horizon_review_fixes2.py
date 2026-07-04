"""Regression tests for the second round of PR#18 review fixes."""

import zipfile
from pathlib import Path

from horizon.audit import AuditLog
from horizon.chaining import OGLRecord, RunsheetNote
from horizon.config import HorizonConfig
from horizon.foundation import _safe_extractall, unzip_archives
from horizon.main import main
from horizon.models import REVIEW_TAG
from horizon.pipeline import chain_to_report
from horizon.report_io import write_report
from horizon.models import ReportModel, TitleRow


# -- duplicate OGL rows must not double-chain ------------------------------
def test_duplicate_ogl_not_reconciled_twice():
    records = [
        OGLRecord(instrument_number="1", grantor="ROOT", grantee="X",
                  conveyed_interest="1/2", legal_description="Sec 31"),
        # same instrument number again -> must NOT advance the ledger again
        OGLRecord(instrument_number="1", grantor="ROOT", grantee="X",
                  conveyed_interest="1/2", legal_description="Sec 31"),
    ]
    notes = [RunsheetNote(instrument_number="1")]
    build = chain_to_report(records, notes)
    # exactly one reconciled row + one duplicate review row
    reconciled = [r for r in build.report.rows if r.retained_interest]
    dups = [r for r in build.report.rows if "duplicate instrument" in r.remarks]
    assert len(reconciled) == 1
    assert len(dups) == 1
    assert dups[0].retained_interest == ""   # no interest math on the duplicate
    assert dups[0].status == REVIEW_TAG


# -- zip path traversal (Zip-Slip) -----------------------------------------
def test_safe_extractall_blocks_traversal(tmp_path):
    archive = tmp_path / "evil.zip"
    dest = tmp_path / "out"
    dest.mkdir()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("good.txt", "ok")
        zf.writestr("../escape.txt", "pwned")  # attempts to escape dest
    with zipfile.ZipFile(archive) as zf:
        skipped = _safe_extractall(zf, dest)
    assert skipped == 1
    assert (dest / "good.txt").exists()
    # the traversal target must NOT have been written outside dest
    assert not (tmp_path / "escape.txt").exists()


def test_unzip_archives_reports_unsafe(tmp_path):
    root = tmp_path / "Horizon"
    root.mkdir()
    cfg = HorizonConfig(root=root)
    cfg.ensure_workspace()
    audit = AuditLog(path=None, echo=False)
    archive = root / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("inner/ok.csv", "a,b\n1,2\n")
        zf.writestr("../../evil.csv", "x")
    unzip_archives(cfg, audit)
    assert not (tmp_path.parent / "evil.csv").exists()
    assert list(cfg.temp_raw.rglob("ok.csv"))


# -- exit codes ------------------------------------------------------------
def test_no_report_returns_nonzero(tmp_path):
    root = tmp_path / "Horizon"
    root.mkdir()
    (root / "note.txt").write_text("nothing usable here")
    # no reference workbook, no seed report -> should NOT report success
    rc = main(["--root", str(root), "--no-backup"])
    assert rc == 3


def test_max_loops_zero_is_success(tmp_path):
    root = tmp_path / "Horizon"
    root.mkdir()
    cfg = HorizonConfig(root=root)
    cfg.ensure_workspace()
    base = "31-12N-24W_Roger_Mills_Cursory_Title_Report"
    seed = ReportModel(section="31-12N-24W", rows=[
        TitleRow(grantor="A", grantee="B", instrument_number="1")])
    write_report(seed, cfg.final_reports / f"{base}_v001.xlsx")
    rc = main(["--root", str(root), "--no-backup", "--max-loops", "0"])
    assert rc == 0  # loop disabled is a deliberate no-op success
