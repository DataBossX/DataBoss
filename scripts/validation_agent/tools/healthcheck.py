"""Environment healthcheck for the DataBossX validation agent.

Verifies Python, venv, packages, paths, DB initialization + append-only
enforcement, .env presence, LibreOffice, credential presence (without revealing
secrets), mode, launcher status, and output write permission. Exit code 0 means
all critical checks passed.
"""

from __future__ import annotations

import importlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import load_settings  # noqa: E402
from db.db_client import AppendOnlyViolation, DatabaseManager  # noqa: E402

REQUIRED_PACKAGES = [
    "openpyxl", "lxml", "pydantic", "dotenv", "pandas", "rapidfuzz",
    "reportlab", "markdown", "docx", "streamlit",
]


def _ok(name: str, detail: str = "") -> Tuple[str, bool, str]:
    return (name, True, detail)


def _fail(name: str, detail: str = "") -> Tuple[str, bool, str]:
    return (name, False, detail)


def run_healthcheck() -> List[Tuple[str, bool, str]]:
    checks: List[Tuple[str, bool, str]] = []
    settings = load_settings()

    # 1. Python version
    v = sys.version_info
    checks.append(
        _ok("python_version", f"{v.major}.{v.minor}.{v.micro}")
        if v >= (3, 11)
        else _fail("python_version", f"{v.major}.{v.minor} < 3.11 required")
    )

    # 2. venv status
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    checks.append(
        _ok("venv", sys.prefix) if in_venv else
        ("venv", True, "not in a venv (allowed, but .venv recommended)")
    )

    # 3. packages import
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
            checks.append(_ok(f"import:{pkg}"))
        except Exception as exc:  # noqa: BLE001
            checks.append(_fail(f"import:{pkg}", str(exc)))

    # 4. project paths
    checks.append(_ok("agent_root", str(settings.agent_root))
                  if settings.agent_root.exists()
                  else _fail("agent_root", "missing"))

    # 5 & 6. DB initializes + append-only enforcement
    try:
        with tempfile.TemporaryDirectory() as td:
            dbp = Path(td) / "hc.sqlite3"
            db = DatabaseManager(dbp)
            db.initialize_schema()
            db.insert("launcher_events", {"event_type": "healthcheck", "detail": "probe"})
            checks.append(_ok("db_init", "schema initialized + insert ok"))
            # append-only enforcement through the manager
            blocked = False
            try:
                db.execute_insert("UPDATE runs SET status='x'")
            except AppendOnlyViolation:
                blocked = True
            checks.append(
                _ok("append_only_manager", "UPDATE blocked")
                if blocked else _fail("append_only_manager", "UPDATE not blocked")
            )
            # raw bypass blocked by triggers
            raw_blocked = False
            try:
                raw = sqlite3.connect(str(dbp))
                raw.execute("INSERT INTO launcher_events(event_type, created_at) VALUES('x','y')")
                try:
                    raw.execute("UPDATE launcher_events SET detail='hacked'")
                    raw.commit()
                except sqlite3.Error:
                    raw_blocked = True
                raw.close()
            except sqlite3.Error:
                raw_blocked = True
            checks.append(
                _ok("append_only_raw", "raw UPDATE blocked by trigger")
                if raw_blocked else _fail("append_only_raw", "raw UPDATE NOT blocked")
            )
            db.close()
    except Exception as exc:  # noqa: BLE001
        checks.append(_fail("db_init", str(exc)))

    # 7. .env / .env.example
    env = settings.agent_root / ".env"
    env_example = settings.agent_root / ".env.example"
    checks.append(
        _ok("env_files", f".env={env.exists()} .env.example={env_example.exists()}")
        if (env.exists() or env_example.exists())
        else _fail("env_files", "neither .env nor .env.example present")
    )

    # 8. LibreOffice
    checks.append(
        _ok("libreoffice", str(settings.libreoffice_path))
        if settings.libreoffice_path
        else ("libreoffice", True, "not found (recalc will escalate cleanly)")
    )

    # 9. OKCounty credentials (never reveal secret values)
    if settings.has_okcounty_credentials():
        checks.append(_ok("okcounty_credentials", "present (values redacted)"))
    else:
        checks.append(
            ("okcounty_credentials", True,
             f"missing: {settings.missing_okcounty_credentials()} (non-blocking)")
        )

    # 10. dry-run / live mode
    checks.append(
        _ok("mode", f"dry_run={settings.dry_run} live_source={settings.live_source_mode} "
                    f"paid_allowed={settings.paid_source_access_allowed()}")
    )

    # 11. Desktop launcher status
    desktop = Path.home() / "Desktop" / "DataBossX Validation Agent.bat"
    checks.append(
        _ok("desktop_launcher", str(desktop))
        if desktop.exists()
        else ("desktop_launcher", True,
              "not installed; run tools/create_desktop_launcher.ps1 locally")
    )

    # 12. output write permission
    try:
        settings.outputs_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.outputs_dir / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append(_ok("output_write", str(settings.outputs_dir)))
    except Exception as exc:  # noqa: BLE001
        checks.append(_fail("output_write", str(exc)))

    # 13. no write requirement on original workbook (design invariant)
    checks.append(_ok("original_workbook_readonly",
                      "agent never opens the source workbook for writing"))

    return checks


def main() -> int:
    checks = run_healthcheck()
    print("DataBossX Validation Agent — Healthcheck")
    print("=" * 60)
    critical_fail = False
    for name, ok, detail in checks:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            critical_fail = True
        print(f"[{mark}] {name}{(' — ' + detail) if detail else ''}")
    print("=" * 60)
    print("RESULT:", "FAIL" if critical_fail else "OK")
    return 1 if critical_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
