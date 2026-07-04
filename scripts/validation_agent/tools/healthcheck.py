"""
Healthcheck — verifies the environment before launching.

Exit code 0 = healthy enough to launch; non-zero = a blocker was found.
Prints a readable report; never prints secrets.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _ok(b: bool) -> str:
    return "OK " if b else "XX "


def main() -> int:
    problems = []
    lines = ["DataBossX Validation Agent — Healthcheck", "=" * 42]

    # 1. Python version
    py_ok = sys.version_info >= (3, 11)
    lines.append(f"{_ok(py_ok)}Python {sys.version.split()[0]} (need >= 3.11)")
    if not py_ok:
        problems.append("Python < 3.11")

    # 2. venv active
    in_venv = (hasattr(sys, "real_prefix") or sys.prefix != getattr(sys, "base_prefix", sys.prefix))
    lines.append(f"{_ok(in_venv)}Virtual environment active: {in_venv}")

    # 3. Required packages
    required = ["openpyxl"]
    optional = ["streamlit", "lxml", "pydantic", "pandas", "rapidfuzz", "reportlab",
                "markdown", "docx", "dotenv"]
    for m in required:
        try:
            importlib.import_module(m)
            lines.append(f"{_ok(True)}required package: {m}")
        except Exception:
            lines.append(f"{_ok(False)}required package MISSING: {m}")
            problems.append(f"missing required package {m}")
    present = []
    for m in optional:
        try:
            importlib.import_module(m)
            present.append(m)
        except Exception:
            pass
    lines.append(f"   optional packages present: {', '.join(present) or '(none)'}")

    # 4-13. Config, paths, DB, append-only, env, LibreOffice, creds, mode, launcher, perms
    try:
        from config.settings import load_settings
        settings = load_settings()
        settings.ensure_dirs()
        lines.append(f"{_ok(True)}Config loaded. agent_root={settings.agent_root}")
        lines.append(f"{_ok(settings.outputs_dir.exists())}Outputs dir: {settings.outputs_dir}")

        from db.db_client import DatabaseManager, AppendOnlyViolation
        db = DatabaseManager(settings.db_path)
        db.insert("launcher_events", {"event": "healthcheck", "detail": "db init"})
        lines.append(f"{_ok(True)}DB initialises and accepts INSERT")

        # append-only proof
        import sqlite3
        appended_blocked = False
        raw = sqlite3.connect(str(settings.db_path))
        try:
            raw.execute("UPDATE launcher_events SET event='x'")
        except sqlite3.DatabaseError:
            appended_blocked = True
        finally:
            raw.close()
        lines.append(f"{_ok(appended_blocked)}Append-only enforced (raw UPDATE blocked): {appended_blocked}")
        if not appended_blocked:
            problems.append("append-only not enforced")

        # env files
        env_exists = (settings.agent_root / ".env").exists()
        ex_exists = (settings.agent_root / ".env.example").exists()
        lines.append(f"{_ok(env_exists or ex_exists)}.env present: {env_exists} / .env.example: {ex_exists}")

        # LibreOffice
        from recalc.libreoffice_runner import detect_libreoffice
        lo = detect_libreoffice(settings.libreoffice_path)
        lines.append(f"{_ok(bool(lo))}LibreOffice: {lo or 'NOT FOUND (recalc will escalate)'}")

        # credentials (presence only — never printed)
        creds = bool(settings.okcounty_username and settings.okcounty_password)
        lines.append(f"   OKCounty credentials configured: {creds}")
        lines.append(f"   Mode: {'LIVE' if settings.live_enabled() else 'DRY-RUN (default)'}")

        # launcher on desktop (best-effort check)
        desktop = Path.home() / "Desktop" / "DataBossX Validation Agent.bat"
        lines.append(f"   Desktop launcher present: {desktop.exists()} ({desktop})")

        # write perms under outputs; source read-only requirement
        test = settings.outputs_dir / ".write_test"
        try:
            test.write_text("ok", encoding="utf-8")
            test.unlink()
            lines.append(f"{_ok(True)}Write permission under outputs/: yes")
        except Exception:
            lines.append(f"{_ok(False)}Write permission under outputs/: NO")
            problems.append("no write permission under outputs")
    except Exception as e:
        lines.append(f"{_ok(False)}Fatal healthcheck error: {e}")
        problems.append(str(e))

    lines.append("=" * 42)
    if problems:
        lines.append(f"RESULT: {len(problems)} blocker(s): " + "; ".join(problems))
    else:
        lines.append("RESULT: healthy")
    print("\n".join(lines))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
