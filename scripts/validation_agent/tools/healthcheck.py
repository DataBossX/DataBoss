"""Healthcheck for the DataBossX Validation Agent.

Verifies the runtime environment without revealing secrets. Exit code 0 means
all *critical* checks passed; non-zero means at least one critical check failed.
Non-critical items (LibreOffice, credentials) are reported but never fail the
check on their own.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

# Make the agent root importable when run directly.
AGENT_ROOT = Path(__file__).resolve().parent.parent
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

REQUIRED_PACKAGES = [
    "streamlit", "openpyxl", "lxml", "pydantic", "dotenv", "pandas",
    "rapidfuzz", "reportlab", "markdown", "docx",
]


def _ok(label: str, detail: str = "") -> tuple[str, bool, str]:
    return (label, True, detail)


def _bad(label: str, detail: str = "") -> tuple[str, bool, str]:
    return (label, False, detail)


def run_healthcheck() -> tuple[list, list]:
    critical: list[tuple[str, bool, str]] = []
    advisory: list[tuple[str, bool, str]] = []

    # 1. Python version
    v = sys.version_info
    if v >= (3, 11):
        critical.append(_ok("Python >= 3.11", f"{v.major}.{v.minor}.{v.micro}"))
    else:
        critical.append(_bad("Python >= 3.11", f"found {v.major}.{v.minor}"))

    # 2. Virtual env active
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    advisory.append((("venv active" if in_venv else "venv NOT active"),
                     in_venv, sys.prefix))

    # 3. Required packages
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
            critical.append(_ok(f"package: {pkg}"))
        except Exception as e:
            critical.append(_bad(f"package: {pkg}", str(e)))

    # 4/12. Paths + outputs writable
    try:
        from config.settings import get_settings
        s = get_settings(refresh=True)
        critical.append(_ok("config loads", str(s.agent_root)))
        s.ensure_dirs()
        probe = s.outputs_dir / ".healthcheck_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        critical.append(_ok("outputs writable", str(s.outputs_dir)))
    except Exception as e:
        critical.append(_bad("config/outputs", str(e)))
        s = None

    # 5/6. DB initializes + append-only enforcement
    try:
        from db.db_client import DatabaseManager, AppendOnlyViolation
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            db = DatabaseManager(Path(t) / "hc.db")
            db.record_launcher_event("healthcheck", "probe")
            blocked = False
            try:
                db.execute("UPDATE launcher_events SET event_type='x'")
            except AppendOnlyViolation:
                blocked = True
            db.close()
            if blocked:
                critical.append(_ok("append-only enforced"))
            else:
                critical.append(_bad("append-only enforced", "UPDATE not blocked"))
    except Exception as e:
        critical.append(_bad("DB init", str(e)))

    # 7. .env / .env.example present
    env_ok = (AGENT_ROOT / ".env").exists() or (AGENT_ROOT / ".env.example").exists()
    advisory.append(("env template present", env_ok, ""))

    # 8. LibreOffice
    try:
        from recalc.libreoffice_runner import detect_libreoffice
        lo = detect_libreoffice(s.libreoffice_path if s else "")
        advisory.append(("LibreOffice available", bool(lo), lo or "not found"))
    except Exception as e:
        advisory.append(("LibreOffice check", False, str(e)))

    # 9/10. Credentials + mode (no secrets revealed)
    if s:
        advisory.append(("OKCounty credentials configured",
                         s.okcounty_configured(),
                         "present" if s.okcounty_configured() else "absent"))
        advisory.append((f"mode = {'dry_run' if s.dry_run else 'live'}",
                         True, f"live_source={s.live_source}"))

    # 11. Desktop launcher
    launcher = AGENT_ROOT / "tools" / "launch_dashboard.bat"
    advisory.append(("dashboard launcher present", launcher.exists(),
                     str(launcher)))

    # 13. No write perm required on source (informational)
    advisory.append(("source workbooks opened read-only", True,
                     "guaranteed by design (copy-to-baseline)"))

    return critical, advisory


def main() -> int:
    critical, advisory = run_healthcheck()
    print("=== DataBossX Validation Agent — Healthcheck ===\n")
    print("CRITICAL:")
    all_ok = True
    for label, ok, detail in critical:
        mark = "PASS" if ok else "FAIL"
        all_ok = all_ok and ok
        print(f"  [{mark}] {label}" + (f"  ({detail})" if detail else ""))
    print("\nADVISORY:")
    for label, ok, detail in advisory:
        mark = "ok " if ok else "note"
        print(f"  [{mark}] {label}" + (f"  ({detail})" if detail else ""))
    print("\nRESULT:", "HEALTHY" if all_ok else "DEGRADED (see FAIL above)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
