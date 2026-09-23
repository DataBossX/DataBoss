from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "runtime",
    "output",
    ".pytest_cache",
    "dist",
    "build",
}


def census_repository(repo_root: str | Path) -> dict:
    root = Path(repo_root)
    counts: Counter[str] = Counter()
    python_modules = 0
    tests = 0
    docs = 0
    workflows = 0
    ai_folders = []
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_dir():
            if path.name.startswith("_AI_"):
                ai_folders.append(path.name)
            continue
        suffix = path.suffix.lower() or path.name
        counts[suffix] += 1
        rel = path.relative_to(root)
        if suffix == ".py":
            python_modules += 1
            if rel.parts[0] == "tests" or path.name.startswith("test_"):
                tests += 1
        if suffix == ".md":
            docs += 1
        if rel.parts[:2] == (".github", "workflows"):
            workflows += 1
    return {
        "repo_root": str(root),
        "python_modules": python_modules,
        "tests": tests,
        "docs": docs,
        "workflows": workflows,
        "ai_folders": sorted(ai_folders),
        "by_suffix": dict(sorted(counts.items())),
        "unknown_is_not_zero": True,
        "client_corpus_present": "UNKNOWN",
    }


def write_census(repo_root: str | Path, dest: str | Path) -> dict:
    census = census_repository(repo_root)
    Path(dest).write_text(json.dumps(census, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return census
