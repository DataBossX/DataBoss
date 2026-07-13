"""Fail CI when the public tree contains client or private operational data.

This is an *additional, independent* gate to the dedicated Gitleaks credential
workflow. Gitleaks alone is not sufficient: it targets credentials, not client
identifiers, cloud drive IDs, private paths, owner data, evidence hashes, or
final/client work products. This gate rejects those in any git-tracked file.

The gate is intentionally allowlist-oriented for its own definition files (which
necessarily contain the denied patterns as detection rules) and denylist-based
for everything else.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

# Binary / non-text suffixes are skipped for content scanning.
IGNORED_SUFFIXES = {
    ".db", ".gif", ".ico", ".jpeg", ".jpg", ".pdf", ".png", ".sqlite",
    ".sqlite3", ".webp", ".zip", ".lock", ".woff", ".woff2",
    ".ttf", ".eot", ".map",
}

OOXML_SUFFIXES = {".xlsx", ".xlsm"}

# Files whose *content* is exempt because they define the policy itself.
CONTENT_ALLOWLIST = {
    "scripts/check_publication_policy.py",
    "tests/test_publication_policy.py",
}

# Tracked paths that must never exist in the public tree.
PATH_DENY_GLOBS = (
    "examples/beckham-section-32.manifest.json",
    "projects/OK-*/*",
    "projects/OK-*",
    "private_projects/*",
    "client_work/*",
    "evidence/*",
    "*/final_delivery/*",
    "*final_delivery*",
    "*FINAL*.xlsx",
    "*CLIENT*.xlsx",
)

# (compiled pattern, human-readable reason)
_CONTENT_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"OK-BECKHAM-32-11N-25W"), "known client project identifier"),
    (re.compile(r"DBX-OK-BECKHAM"), "known client project identifier"),
    (re.compile(r"beckham-section-32"), "known client project identifier"),
    (re.compile(r"11N 25W 32"), "known client legal description / source root"),
    (re.compile(r"FINAL_VERIFIED"), "final/client work-product marker"),
    (re.compile(r"\bDiversified\b"), "known client/interest-owner entity name"),
    (re.compile(r"Ella Pearl Kirk"), "owner personal data"),
    (
        re.compile(r"drive\.google\.com/(?:file/d/|drive/folders/|open\?id=)[A-Za-z0-9_-]{20,}"),
        "Google Drive cloud identifier",
    ),
    (
        re.compile(r'(?i)"(?:id|folder_id|file_id|drive_id)"\s*:\s*"[A-Za-z0-9_-]{28,}"'),
        "cloud drive identifier in structured data",
    ),
)

_REPORTED_HASH = re.compile(r'"reported_sha256"\s*:\s*"([0-9a-f]{64})"')


def _looks_synthetic_hash(value: str) -> bool:
    if len(set(value)) <= 2:
        return True
    for unit in ("deadbeef", "cafebabe", "0123456789abcdef", "abcdef", "feedface"):
        if unit and set(value) <= set(unit) and value == (unit * (64 // len(unit) + 1))[:64]:
            return True
    # Repeating short pattern (e.g. deadbeef repeated) is synthetic.
    for size in (2, 4, 8, 16):
        if value == (value[:size] * (64 // size)):
            return True
    return False


def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"])
    return [Path(item.decode()) for item in output.split(b"\0") if item]


def _posix(path: Path) -> str:
    return path.as_posix()


def _ooxml_text(path: Path) -> str:
    """Extract visible cell/comment text from an OOXML workbook package."""
    parts: list[str] = []
    try:
        with zipfile.ZipFile(path) as package:
            for name in package.namelist():
                if not name.endswith(".xml"):
                    continue
                if not (
                    name.startswith("xl/sharedStrings")
                    or name.startswith("xl/worksheets/")
                    or name.startswith("xl/comments")
                ):
                    continue
                try:
                    root = ET.fromstring(package.read(name))
                except (ET.ParseError, KeyError, zipfile.BadZipFile):
                    continue
                for element in root.iter():
                    if not element.tag.endswith("}t") and element.tag != "t":
                        continue
                    if element.text:
                        parts.append(element.text)
    except (OSError, zipfile.BadZipFile):
        return ""
    return "\n".join(parts)


def _scan_text(path: Path, posix: str, text: str, findings: list[str]) -> None:
    for pattern, reason in _CONTENT_RULES:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"{posix}:{line}: {reason}")
    for match in _REPORTED_HASH.finditer(text):
        digest = match.group(1)
        if not _looks_synthetic_hash(digest):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"{posix}:{line}: real-looking evidence hash in manifest")


def path_findings(files: list[Path]) -> list[str]:
    findings = []
    for path in files:
        text = _posix(path)
        for pattern in PATH_DENY_GLOBS:
            if fnmatch.fnmatch(text, pattern):
                findings.append(f"{text}: forbidden path (matches {pattern!r})")
                break
    return findings


def content_findings(files: list[Path]) -> list[str]:
    findings = []
    for path in files:
        posix = _posix(path)
        if posix in CONTENT_ALLOWLIST:
            continue
        suffix = path.suffix.lower()
        if suffix in IGNORED_SUFFIXES:
            continue
        if suffix in OOXML_SUFFIXES:
            _scan_text(path, posix, _ooxml_text(path), findings)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        _scan_text(path, posix, text, findings)
    return findings


def scan() -> list[str]:
    files = tracked_files()
    return sorted(set(path_findings(files) + content_findings(files)))


def main() -> int:
    findings = scan()
    if findings:
        print("Publication-policy violations found in tracked files:", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1
    print("Publication-policy check passed: no client or private data in tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
