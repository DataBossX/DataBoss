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
IGNORED_NAMES = {".env.example"}
ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:export\s+)?[A-Z0-9_]*(?:API_KEY|TOKEN|PASSWORD|SECRET|PRIVATE_KEY)"
    r"[ \t]*[:=][ \t]*['\"]?([^'\"\s#]+)"
)
TOKEN_PATTERNS = (
    re.compile("sk-" + r"[A-Za-z0-9_-]{20,}"),
    re.compile("gh" + r"[pousr]_[A-Za-z0-9]{20,}"),
    re.compile("AIza" + r"[A-Za-z0-9_-]{20,}"),
)
PLACEHOLDERS = {"", "changeme", "example", "placeholder", "redacted", "your_key_here"}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"])
    return [Path(item.decode()) for item in output.split(b"\0") if item]


def scan() -> list[str]:
    findings = []
    for path in tracked_files():
        if path.name in IGNORED_NAMES or path.suffix.lower() in IGNORED_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in ASSIGNMENT.finditer(text):
            value = match.group(1).strip().lower()
            if (
                value not in PLACEHOLDERS
                and not value.startswith(("${", "os.getenv(", "os.environ"))
            ):
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
