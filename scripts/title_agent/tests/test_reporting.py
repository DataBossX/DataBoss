"""Tests for core/reporting.py — the Certified Workbook + Audit Report."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ..core.loop import LoopState, PerfectionLoop
from ..core.memory import AuditLogger, SQLiteManager, VersionController
from ..core.reporting import CertificationReporter, ReportExistsError


def _seed(tmp: Path):
    mgr = SQLiteManager(tmp / "s.db")
    vc = VersionController(mgr, workbook_dir=tmp / "wb")
    v1 = vc.mint_new_version("TitleReport", reason="ingest initial workbook")
    v1.file_path.write_bytes(b"PK\x03\x04 certified workbook bytes")
    AuditLogger(mgr).log_action("GATE_EVALUATION", "TitleReport _v001", "PASS")
    return mgr, vc, v1


def test_generates_both_artifacts(tmp: Path) -> None:
    mgr, vc, v1 = _seed(tmp)
    reporter = CertificationReporter(mgr, output_dir=tmp / "reports")
    arts = reporter.generate(v1)
    assert arts.certified_workbook.exists() and arts.audit_report.exists()
    # Certified workbook is a byte-for-byte copy of the certified version.
    assert arts.certified_workbook.read_bytes() == v1.file_path.read_bytes()
    report = arts.audit_report.read_text(encoding="utf-8")
    assert "Certification Report" in report
    assert "25-004" in report and "637.42" in report
    assert "_v001" in report
    # All six gates listed as PASS.
    assert report.count("✅ PASS") == 6
    # The generation itself is audited.
    actions = [r.action for r in AuditLogger(mgr).read_all()]
    assert "CERTIFICATION_REPORT" in actions


def test_refuses_to_overwrite(tmp: Path) -> None:
    mgr, vc, v1 = _seed(tmp)
    reporter = CertificationReporter(mgr, output_dir=tmp / "reports")
    reporter.generate(v1)
    try:
        reporter.generate(v1)  # same version again
    except ReportExistsError:
        return
    raise AssertionError("regenerating for the same version must not overwrite")


def test_loop_invokes_on_certified_hook(tmp: Path) -> None:
    mgr = SQLiteManager(tmp / "s.db")
    vc = VersionController(mgr, workbook_dir=tmp / "wb")
    v1 = vc.mint_new_version("TitleReport", reason="init")
    v1.file_path.write_bytes(b"PK\x03\x04 wb")
    reporter = CertificationReporter(mgr, output_dir=tmp / "reports")

    captured: dict[str, object] = {}

    class _CleanEval:
        def evaluate(self, version): return []

    class _Repairer:
        def apply(self, failures, old_version, new_version): ...

    loop = PerfectionLoop(
        mgr, "TitleReport", _CleanEval(), _Repairer(), versions=vc,
        on_certified=lambda v: captured.__setitem__("arts", reporter.generate(v)),
    )
    outcome = loop.run()
    assert outcome.state == LoopState.CERTIFIED
    assert "arts" in captured  # the hook ran and produced artifacts


def _run_all() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(tests)} passed.")


if __name__ == "__main__":
    _run_all()
