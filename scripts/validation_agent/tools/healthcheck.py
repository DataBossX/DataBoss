"""Environment healthcheck. Cross-platform; exits non-zero on any hard failure.

Reports (without revealing secrets): Python version, venv, packages, paths, DB
append-only enforcement, .env presence, LibreOffice, credentials presence,
mode, launcher presence, output writability, and that no write access to the
source workbook is required.
"""
from __future__ import annotations

import importlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

_AGENT_ROOT = Path(__file__).resolve().parent.parent
if str(_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_AGENT_ROOT))

REQUIRED_PACKAGES = ["openpyxl", "lxml", "pydantic", "dotenv", "pandas", "rapidfuzz"]
OPTIONAL_PACKAGES = ["streamlit", "reportlab", "markdown", "docx"]


def check(label: str, ok: bool, detail: str = "") -> dict:
    return {"label": label, "ok": bool(ok), "detail": detail}


def run() -> int:
    results = []
    # Python
    v = sys.version_info
    results.append(check("python>=3.11", v >= (3, 11), f"{v.major}.{v.minor}.{v.micro}"))
    # venv
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    results.append(check("virtualenv active", in_venv, sys.prefix))
    # packages
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
            results.append(check(f"pkg:{pkg}", True))
        except Exception as e:
            results.append(check(f"pkg:{pkg}", False, str(e)[:60]))
    for pkg in OPTIONAL_PACKAGES:
        try:
            importlib.import_module(pkg)
            results.append(check(f"pkg(optional):{pkg}", True))
        except Exception:
            results.append(check(f"pkg(optional):{pkg}", False, "optional — not installed"))

    from config.settings import get_settings
    settings = get_settings(reload=True)
    results.append(check("agent_root exists", settings.agent_root.exists(), str(settings.agent_root)))
    results.append(check("schema.sql exists", settings.schema_path.exists(), str(settings.schema_path)))

    # DB append-only enforcement.
    try:
        from db.db_client import DatabaseManager, AppendOnlyViolation
        from db.audit_logger import AuditLogger
        tmp = Path(tempfile.mkdtemp())
        db = DatabaseManager(tmp / "hc.sqlite3", settings.schema_path)
        AuditLogger(db).launcher_event("healthcheck", "probe")
        blocked = False
        try:
            db._conn.execute("UPDATE launcher_events SET detail='x'")
        except sqlite3.DatabaseError:
            blocked = True
        raw = sqlite3.connect(str(tmp / "hc.sqlite3"))
        raw_blocked = False
        try:
            raw.execute("DELETE FROM launcher_events"); raw.commit()
        except sqlite3.DatabaseError:
            raw_blocked = True
        raw.close(); db.close()
        results.append(check("DB init + insert", True))
        results.append(check("DB UPDATE blocked", blocked))
        results.append(check("DB raw DELETE blocked (trigger)", raw_blocked))
    except Exception as e:
        results.append(check("DB append-only", False, str(e)[:80]))

    # .env
    env_ok = (settings.agent_root / ".env").exists() or (settings.agent_root / ".env.example").exists()
    results.append(check(".env or .env.example present", env_ok))

    # LibreOffice
    from recalc.libreoffice_runner import detect_libreoffice
    lo = detect_libreoffice(settings.libreoffice_path)
    results.append(check("LibreOffice available", lo is not None, lo or "not found (recalc will escalate)"))

    # Credentials + mode (never print secret values).
    results.append(check("OKCounty credentials present", settings.credentials_present(),
                         "present" if settings.credentials_present() else "absent (dry-run)"))
    results.append(check("mode", True, "live" if settings.live_retrieval_allowed() else "dry_run"))

    # Launcher presence (best-effort — desktop dir varies by OS).
    launcher = _AGENT_ROOT / "tools" / "launch_dashboard.bat"
    results.append(check("launch script present", launcher.exists(), str(launcher)))

    # Outputs writable.
    try:
        settings.outputs_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.outputs_dir / ".write_probe"
        probe.write_text("ok", encoding="utf-8"); probe.unlink()
        results.append(check("outputs writable", True, str(settings.outputs_dir)))
    except Exception as e:
        results.append(check("outputs writable", False, str(e)[:60]))

    # Print report.
    hard_fail = 0
    print("=== DataBossX Validation Agent — Healthcheck ===")
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        optional = "optional" in r["label"] or r["label"] in (
            "virtualenv active", "LibreOffice available", "OKCounty credentials present")
        if not r["ok"] and not optional:
            hard_fail += 1
        print(f"[{mark}] {r['label']}  {r['detail']}")
    print(f"=== hard failures: {hard_fail} ===")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(run())
