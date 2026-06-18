#!/usr/bin/env python3
"""Run all relevant checks for DataBossX in a sensible order.

Steps (each is skipped gracefully if its tool is unavailable):
  1. pytest (Python unit/smoke tests)
  2. flake8 syntax-error gate (matches CI)
  3. frontend lint (if node_modules present)

Usage:
    python scripts/test_all.py
Exit code is non-zero if any executed step fails.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
failures: list[str] = []
skipped: list[str] = []


def have(mod_or_cmd: str, is_module: bool = False) -> bool:
    if is_module:
        try:
            __import__(mod_or_cmd)
            return True
        except Exception:
            return False
    return shutil.which(mod_or_cmd) is not None


def run(label: str, cmd: list[str], cwd: Path = ROOT) -> None:
    print(f"\n=== {label} ===\n$ {' '.join(cmd)}")
    rc = subprocess.run(cmd, cwd=cwd).returncode
    if rc != 0:
        failures.append(label)
        print(f"--- {label}: FAILED (exit {rc}) ---")
    else:
        print(f"--- {label}: passed ---")


def main() -> int:
    # 1. pytest
    if have("pytest", is_module=True):
        run("pytest", [sys.executable, "-m", "pytest", "-q"])
    else:
        skipped.append("pytest (not installed)")

    # 2. flake8 syntax gate (same as CI)
    if have("flake8", is_module=True):
        run("flake8 (syntax errors)",
            [sys.executable, "-m", "flake8", ".", "--count",
             "--select=E9,F63,F7,F82", "--show-source", "--statistics"])
    else:
        skipped.append("flake8 (not installed)")

    # 3. frontend lint (only if deps already installed)
    fe = ROOT / "frontend"
    if (fe / "node_modules").exists() and have("npx"):
        run("frontend eslint", ["npx", "eslint", "src", "--max-warnings", "0"],
            cwd=fe)
    else:
        skipped.append("frontend eslint (node_modules not installed)")

    print("\n" + "=" * 60)
    if skipped:
        print("Skipped:")
        for s in skipped:
            print(f"  - {s}")
    if failures:
        print("FAILED steps: " + ", ".join(failures))
        print("=" * 60)
        return 1
    print("All executed checks passed.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
