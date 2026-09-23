from __future__ import annotations

import re
from pathlib import Path


FORBIDDEN = [
    (re.compile(r"(?i)(api[_-]?key|secret[_-]?key|xoxb-|sk-[A-Za-z0-9]{20,})"), "credential"),
    (re.compile(r"[A-Za-z]:\\(?:Users|DataBoss|Desktop)\\"), "private_windows_path"),
    (re.compile(r"(?i)-----BEGIN (RSA |OPENSSH |PRIVATE )"), "private_key"),
]

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "runtime", "output"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".json", ".sql", ".env.example"}

# Architecture docs may mention example Windows roots as operator instructions.
ALLOWLIST = {
    "RUNBOOK.md",
    "TODO_NOW.md",
    "PROJECT_STATUS.md",
    "grocery_report_pipeline.py",
    "horizon/README.md",
    "horizon/main.py",
    "Run_Horizon.bat",
    "docs/DATABOSSX_OS_BLUEPRINT.md",
}


def scan_publication_policy(repo_root: str | Path) -> dict:
    root = Path(repo_root)
    findings = []
    scanned = 0
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".env.example":
            continue
        rel = path.relative_to(root).as_posix()
        scanned += 1
        if rel in ALLOWLIST or rel.startswith("_AI_"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for rx, kind in FORBIDDEN:
            if rx.search(text):
                findings.append({"path": rel, "kind": kind})
                break
    return {
        "scanned": scanned,
        "findings": findings,
        "status": "FAIL" if findings else "PASS",
    }
