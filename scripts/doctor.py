#!/usr/bin/env python3
"""DataBossX environment doctor.

Read-only health check for operators. Verifies runtimes, project layout, env
templates, and common misconfigurations. Never prints secret values.

Usage:
    python scripts/doctor.py
Exit code is non-zero if any hard requirement is missing.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OK = "[ OK ]"
WARN = "[WARN]"
FAIL = "[FAIL]"

problems = 0
warnings = 0


def check(label: str, ok: bool, detail: str = "", hard: bool = True) -> None:
    global problems, warnings
    if ok:
        print(f"{OK} {label}" + (f" — {detail}" if detail else ""))
    elif hard:
        problems += 1
        print(f"{FAIL} {label}" + (f" — {detail}" if detail else ""))
    else:
        warnings += 1
        print(f"{WARN} {label}" + (f" — {detail}" if detail else ""))


def tool_version(cmd: list[str]) -> str | None:
    exe = shutil.which(cmd[0])
    if not exe:
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception:
        return None


def main() -> int:
    print("=" * 60)
    print("DataBossX Doctor")
    print("=" * 60)

    # --- Runtimes ---
    print("\n-- Runtimes --")
    py = sys.version_info
    check(f"Python >= 3.10 (found {py.major}.{py.minor}.{py.micro})",
          py >= (3, 10))
    node = tool_version(["node", "--version"])
    check("Node.js installed", node is not None, node or "not found", hard=False)
    yarn = tool_version(["yarn", "--version"])
    check("Yarn installed", yarn is not None, yarn or "not found", hard=False)

    # --- Project layout ---
    print("\n-- Project layout --")
    for rel in ["backend/server.py", "requirements.txt",
                "frontend/package.json", "doto_image_commander/app.py",
                "automation/playwright_bot.py", "config/settings.toml"]:
        check(f"exists: {rel}", (ROOT / rel).exists(), hard=False)

    # --- Env templates (names only; never read values) ---
    print("\n-- Environment templates --")
    for rel in [".env.example", "backend/.env.example",
                "frontend/.env.example", "doto_image_commander/.env.example"]:
        check(f"template present: {rel}", (ROOT / rel).exists(), hard=False)

    for env_rel in [".env", "backend/.env", "frontend/.env"]:
        present = (ROOT / env_rel).exists()
        check(f"local env configured: {env_rel}",
              present, "missing (copy from .env.example when running)",
              hard=False)

    # --- Common misconfigurations ---
    print("\n-- Misconfiguration checks --")
    req = (ROOT / "backend" / "requirements.txt")
    if req.exists():
        body = req.read_text(encoding="utf-8", errors="ignore")
        check("backend/requirements.txt has no stdlib 'sqlite3' pin",
              "\nsqlite3" not in ("\n" + body))

    # Secrets must not be tracked by git
    if shutil.which("git"):
        try:
            out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                                 capture_output=True, text=True, timeout=20)
            files = out.stdout.splitlines()
            leaked = [f for f in files
                      if f.endswith(".env") or f.endswith(".key")
                      or f.endswith(".pem") or f.endswith(".db")]
            check("no secrets/db tracked by git",
                  not leaked, ", ".join(leaked) if leaked else "")
        except Exception:
            pass

    # --- Python deps installed? ---
    print("\n-- Python dependency probe --")
    for mod in ["fastapi", "pytest"]:
        try:
            __import__(mod)
            check(f"import {mod}", True)
        except Exception:
            check(f"import {mod}", False,
                  "run: pip install -r requirements.txt", hard=False)

    print("\n" + "=" * 60)
    print(f"Doctor finished: {problems} failure(s), {warnings} warning(s)")
    print("=" * 60)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
