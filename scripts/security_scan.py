#!/usr/bin/env python3
"""Lightweight security scan for DataBossX.

Runs the tools that are available and degrades gracefully when they are not:
  - pip-audit        (Python dependency vulnerabilities)
  - npm audit         (frontend dependency vulnerabilities, if node present)
  - a built-in repo secret/hygiene scan (always runs, no external deps)

Usage:
    python scripts/security_scan.py
This script is advisory: it reports findings but only returns non-zero when the
built-in hygiene scan finds tracked secrets.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),          # OpenAI-style key
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),    # Anthropic-style key
    re.compile(r"AKIA[0-9A-Z]{16}"),             # AWS access key id
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
             "build", "dist", "downloads", "images", ".pytest_cache"}


def run_optional(label: str, cmd: list[str]) -> None:
    if not shutil.which(cmd[0]):
        print(f"[skip] {label}: '{cmd[0]}' not installed")
        return
    print(f"\n=== {label} ===\n$ {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=ROOT, timeout=600)
    except Exception as e:  # noqa: BLE001
        print(f"[warn] {label} failed to run: {e}")


def git_tracked_secrets() -> list[str]:
    if not shutil.which("git"):
        return []
    out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                         capture_output=True, text=True)
    bad = []
    for f in out.stdout.splitlines():
        low = f.lower()
        if low.endswith((".env", ".key", ".pem", ".db", ".sqlite",
                         ".sqlite3")) and not low.endswith(".env.example"):
            bad.append(f)
        if "credentials" in low or low.endswith("token.json"):
            bad.append(f)
    return sorted(set(bad))


def scan_source_for_secrets() -> list[str]:
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".xlsx",
                                   ".lock", ".db", ".sqlite", ".sqlite3"}:
            continue
        # .env / key files are the *legitimate* place for secrets and are
        # gitignored; the git-tracked check above is the real guard. Don't
        # scan (or echo anything about) their contents here.
        name = path.name.lower()
        if (name == ".env" or name.startswith(".env.")) and name != ".env.example":
            continue
        if name.endswith((".key", ".pem", ".crt")) or name == "master.key":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                hits.append(f"{path.relative_to(ROOT)} (matched {pat.pattern})")
                break
    return hits


def main() -> int:
    print("=" * 60)
    print("DataBossX Security Scan")
    print("=" * 60)

    # External dependency audits (best-effort)
    run_optional("pip-audit", ["pip-audit", "-r", "requirements.txt"])
    if (ROOT / "frontend").exists():
        run_optional("npm audit (frontend)",
                     ["npm", "audit", "--prefix", "frontend"])

    # Built-in hygiene scan (always runs)
    print("\n=== built-in hygiene scan ===")
    tracked = git_tracked_secrets()
    if tracked:
        print("[FAIL] git is tracking secret-like files:")
        for f in tracked:
            print(f"   - {f}")
    else:
        print("[ OK ] no secret-like files tracked by git")

    leaks = scan_source_for_secrets()
    if leaks:
        print("[FAIL] possible hardcoded secrets found in source:")
        for f in leaks:
            print(f"   - {f}")
    else:
        print("[ OK ] no obvious hardcoded secrets in source")

    print("\n" + "=" * 60)
    failed = bool(tracked or leaks)
    print("RESULT:", "FINDINGS PRESENT" if failed else "clean")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
