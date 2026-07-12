"""Fail CI when tracked files contain common credential forms."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

IGNORED_SUFFIXES = {
    ".db", ".gif", ".ico", ".jpeg", ".jpg", ".pdf", ".png", ".sqlite", ".sqlite3",
    ".webp", ".xlsx", ".xlsm", ".zip",
}
# NOTE: .env.example files are intentionally NOT blanket-ignored. They are scanned
# like any other tracked file; only recognizable placeholder values are allowed,
# so a real credential accidentally committed to an example template is caught.
ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:export\s+)?[A-Z0-9_]*(?:API_KEY|TOKEN|PASSWORD|SECRET|PRIVATE_KEY)"
    r"[ \t]*[:=][ \t]*['\"]?([^'\"\s#]+)"
)
# A leading boundary keeps provider prefixes from matching inside ordinary words
# (e.g. "sk-" must not match inside "risk-management-...").
_TOKEN_BOUNDARY = r"(?<![A-Za-z0-9])"
TOKEN_PATTERNS = (
    re.compile(_TOKEN_BOUNDARY + "sk-" + r"[A-Za-z0-9_-]{20,}"),
    re.compile(_TOKEN_BOUNDARY + "gh" + r"[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(_TOKEN_BOUNDARY + "AIza" + r"[A-Za-z0-9_-]{20,}"),
)
PLACEHOLDERS = {"", "changeme", "example", "placeholder", "redacted", "your_key_here"}
_PLACEHOLDER_MARKERS = (
    "example", "changeme", "placeholder", "redacted", "your", "...", "here",
    "dummy", "fake", "sample", "xxxx", "<", ">",
)
_ENV_LOOKUP_PREFIXES = ("${", "os.getenv(", "os.environ", "process.env")
# The credential-noun regex is case-insensitive, so it also matches ordinary
# source identifiers such as ``approve_token = _mint(...)`` or ``token: Mapping``.
# A real credential value is an opaque literal, never a code expression, so any
# value carrying code punctuation is treated as source and skipped.
_CODE_VALUE_CHARS = "()[]{}<>"


def _is_code_expression(value: str) -> bool:
    return any(char in value for char in _CODE_VALUE_CHARS)


def _is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in PLACEHOLDERS:
        return True
    if lowered.startswith(_ENV_LOOKUP_PREFIXES):
        return True
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"])
    return [Path(item.decode()) for item in output.split(b"\0") if item]


def scan() -> list[str]:
    findings = []
    for path in tracked_files():
        if path.suffix.lower() in IGNORED_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in ASSIGNMENT.finditer(text):
            value = match.group(1)
            if _is_placeholder(value) or _is_code_expression(value):
                continue
            findings.append(f"{path}:{text.count(chr(10), 0, match.start()) + 1}: credential assignment")
        for pattern in TOKEN_PATTERNS:
            for match in pattern.finditer(text):
                findings.append(f"{path}:{text.count(chr(10), 0, match.start()) + 1}: token-like value")
    return findings


def main() -> int:
    findings = scan()
    if findings:
        print("Potential secrets found in tracked files:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1
    print("No credential patterns found in tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
