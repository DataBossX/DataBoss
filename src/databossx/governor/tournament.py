from __future__ import annotations

import json
from pathlib import Path


BLOCKING_FILES = ("README.md", "RECEIPT.md")
SCORING_HINTS = (
    "issue #94",
    "no fabrication",
    "unknown is not zero",
    "client_bytes_mutated=no",
    "external_release=no",
    "second control",
    "governor",
    "publication",
)
CLIENTISH_TOKENS = ("book 512", "11n 25w 32", "drive.google.com/file")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _folder_files(folder: Path) -> dict[str, Path]:
    if not folder.is_dir():
        return {}
    return {path.name: path for path in folder.iterdir() if path.is_file()}


def score_folder(folder: Path) -> dict:
    files = _folder_files(folder)
    missing = [name for name in BLOCKING_FILES if name not in files]
    blob = "\n".join(_read(path).lower() for path in files.values())
    hints = sum(1 for hint in SCORING_HINTS if hint in blob)
    clientish = any(token in blob for token in CLIENTISH_TOKENS)
    second_os = "new operating system" in blob and "do not create a second" not in blob
    blocked = bool(missing) or clientish or second_os
    score = 0 if blocked else 10 + hints + min(len(files), 8)
    return {
        "folder": folder.name,
        "files": sorted(files),
        "missing_blocking": missing,
        "hint_hits": hints,
        "clientish": clientish,
        "second_os": second_os,
        "blocked": blocked,
        "score": score,
    }


def judge_folders(repo_root: str | Path, prefix: str = "_AI_") -> dict:
    root = Path(repo_root)
    folders = sorted(path for path in root.iterdir() if path.is_dir() and path.name.startswith(prefix))
    scorecards = [score_folder(folder) for folder in folders]
    eligible = [row for row in scorecards if not row["blocked"]]
    winner = max(eligible, key=lambda row: (row["score"], row["folder"]), default=None)
    return {
        "folders_judged": len(scorecards),
        "scorecards": scorecards,
        "winner": None if winner is None else winner["folder"],
        "unknown_is_not_zero": True,
    }


def write_scorecard(repo_root: str | Path, dest: str | Path) -> dict:
    result = judge_folders(repo_root)
    Path(dest).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result
