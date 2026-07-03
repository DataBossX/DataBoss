"""Phase 1 proof-of-correctness tests for core/memory.py.

These are executable assertions of the Golden Law invariants at the storage
layer. Run directly (``python -m scripts.title_agent.tests.test_memory``) or
under pytest. No network, no external services.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from ..core.memory import (
    AuditLogger,
    SQLiteManager,
    VersionController,
    VersionOverwriteError,
)


def _fresh(tmp: Path) -> tuple[SQLiteManager, AuditLogger, VersionController]:
    mgr = SQLiteManager(tmp / "state.db")
    audit = AuditLogger(mgr, audit_log_path=tmp / "audit.log")
    versions = VersionController(mgr, workbook_dir=tmp / "workbooks")
    return mgr, audit, versions


def test_audit_is_insert_only_and_ordered(tmp: Path) -> None:
    _, audit, _ = _fresh(tmp)
    a = audit.log_action("GATE_CHECK", "Gate1/tract-1", "PASS")
    b = audit.log_action("GATE_CHECK", "Gate2/gross", "FAIL", metadata={"delta": 0.01})
    assert b > a
    trail = audit.read_all()
    assert [r.id for r in trail] == [a, b]
    assert trail[1].metadata == {"delta": 0.01}
    # File mirror was written.
    lines = (tmp / "audit.log").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_audit_update_and_delete_are_blocked(tmp: Path) -> None:
    mgr, audit, _ = _fresh(tmp)
    audit.log_action("GATE_CHECK", "Gate1/tract-1", "PASS")
    with mgr.connection() as conn:
        for stmt, params in (
            ("UPDATE audit_log SET result = 'TAMPERED' WHERE id = 1", ()),
            ("DELETE FROM audit_log WHERE id = 1", ()),
        ):
            try:
                conn.execute(stmt, params)
            except sqlite3.IntegrityError:
                continue  # RAISE(ABORT) surfaces as IntegrityError
            except sqlite3.OperationalError:
                continue
            raise AssertionError(f"append-only violation not blocked: {stmt}")
    # History is intact and untouched.
    trail = audit.read_all()
    assert len(trail) == 1 and trail[0].result == "PASS"


def test_examiner_override_is_tagged(tmp: Path) -> None:
    _, audit, _ = _fresh(tmp)
    rid = audit.log_examiner_override(
        "examiner-42", "Gate3/tract-7", "Approved Title Defect Requirement TDR-9"
    )
    rec = next(r for r in audit.read_all() if r.id == rid)
    assert rec.action == AuditLogger.EXAMINER_OVERRIDE
    assert rec.actor == "examiner-42"


def test_versions_are_strictly_sequential(tmp: Path) -> None:
    _, _, versions = _fresh(tmp)
    key = "31-12N-24W_TitleReport"
    assert versions.get_latest_version(key) is None
    v1 = versions.mint_new_version(key, reason="init")
    v2 = versions.mint_new_version(key, reason="MATH_FOOTING_ERROR repair")
    assert (v1.version_number, v2.version_number) == (1, 2)
    assert v1.version_label == "_v001" and v2.version_label == "_v002"
    assert v2.parent_version == 1
    assert versions.get_latest_version(key).version_number == 2
    assert [v.version_number for v in versions.history(key)] == [1, 2]


def test_mint_refuses_to_overwrite_existing_file(tmp: Path) -> None:
    _, _, versions = _fresh(tmp)
    key = "wb"
    v1 = versions.mint_new_version(key, reason="init")
    v1.file_path.write_bytes(b"original")  # caller writes the bytes
    # Simulate a stray file sitting where v2 would land.
    stray = versions.mint_new_version.__self__._dir / "wb_v002.xlsx"  # type: ignore[attr-defined]
    stray.write_bytes(b"stray")
    try:
        versions.mint_new_version(key, reason="repair")
    except VersionOverwriteError:
        pass
    else:
        raise AssertionError("mint should refuse to overwrite an existing file")
    # The prohibited mint must not have left a phantom DB row.
    assert versions.get_latest_version(key).version_number == 1


def test_two_artifacts_track_independently(tmp: Path) -> None:
    _, _, versions = _fresh(tmp)
    a1 = versions.mint_new_version("A", reason="init")
    b1 = versions.mint_new_version("B", reason="init")
    a2 = versions.mint_new_version("A", reason="fix")
    assert a1.version_number == 1 and b1.version_number == 1 and a2.version_number == 2


def _run_all() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(tests)} passed.")


if __name__ == "__main__":
    _run_all()
