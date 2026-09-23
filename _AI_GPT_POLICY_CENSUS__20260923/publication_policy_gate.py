#!/usr/bin/env python3
"""Fail-closed publication checks with redacted command-line output.

This module has no third-party dependencies. It scans a file or directory
without modifying it and exits non-zero when a publication-policy finding is
present. Findings printed by the CLI contain a path digest, never matched text
or a potentially sensitive filename.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


MAX_FILE_BYTES = 8 * 1024 * 1024

IGNORED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "node_modules",
        "out",
        "venv",
    }
)

# These public files are policy, architecture, or synthetic-fixture material.
# The allowlist suppresses only path/Drive/report-pattern findings. Credential
# findings, symlinks, unreadable files, and oversized files are never exempt.
KNOWN_PUBLIC_FILES = frozenset(
    {
        ".gitleaks.toml",
        ".gitignore",
        "SECURITY.md",
        "docs/DATABOSSX_OS_BLUEPRINT.md",
        "docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md",
        "docs/architecture/databossx-os.build-plan.json",
        "examples/projects/SYNTHETIC-DEMO/project_manifest.json",
        "_AI_GPT_POLICY_CENSUS__20260923/PUBLIC_PR_CLASSIFICATION.md",
        "_AI_GPT_POLICY_CENSUS__20260923/README.md",
        "_AI_GPT_POLICY_CENSUS__20260923/RECEIPT.md",
        "_AI_GPT_POLICY_CENSUS__20260923/CENSUS.json",
        "_AI_GPT_POLICY_CENSUS__20260923/publication_policy_gate.py",
        "_AI_GPT_POLICY_CENSUS__20260923/test_publication_policy.py",
    }
)

ARCHITECTURE_PREFIXES = ("docs/architecture/",)
SYNTHETIC_PATH_MARKERS = frozenset(
    {"synthetic", "synthetic-demo", "synthetic_fixtures", "synthetic-fixtures"}
)

PRIVATE_WINDOWS_PATH = re.compile(r"(?i)(?<![A-Za-z0-9])D:\\[^\r\n\"'`<>]{1,260}")
DRIVE_URL = re.compile(
    r"(?i)https?://drive\.google\.com/(?:file/d/|drive/(?:u/\d+/)?folders/)"
    r"[A-Za-z0-9_-]{20,}"
)
DRIVE_ID_ASSIGNMENT = re.compile(
    r"(?i)\b(?:drive|file|folder)[_-]?id\b\s*[:=]\s*[\"']?"
    r"[A-Za-z0-9_-]{20,}[\"']?"
)
PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")
AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
GITHUB_TOKEN = re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{30,}\b")
GOOGLE_API_KEY = re.compile(r"\bAIza[A-Za-z0-9_-]{30,}\b")
SLACK_TOKEN = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")
BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{20,}={0,2}\b")
AUTHORITY_CREDENTIAL = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|"
    r"password|passwd|secret[_-]?key)\b\s*[:=]\s*[\"']([^\"'\r\n]{8,})[\"']"
)

REPORT_REFERENCE = re.compile(
    r"(?i)(?:^|[\s\"'`(])"
    r"([^\s\"'`<>]{0,180}"
    r"(?:client|customer|owner(?:ship)?|title|abstract|"
    r"final[-_ ]?(?:report|delivery)|delivery[-_ ]?(?:report|package)|"
    r"section[-_ ]?\d+)"
    r"[^\s\"'`<>]{0,180}\.(?:xlsx|xlsm|xls|csv|pdf|docx|zip))"
)
SENSITIVE_REPORT_SUFFIXES = frozenset(
    {".csv", ".docx", ".pdf", ".xls", ".xlsm", ".xlsx", ".zip"}
)
SENSITIVE_REPORT_NAME = re.compile(
    r"(?i)(?:client|customer|owner(?:ship)?|title|abstract|"
    r"final[-_ ]?(?:report|delivery)|delivery[-_ ]?(?:report|package)|"
    r"section[-_ ]?\d+)"
)

PLACEHOLDER_WORDS = frozenset(
    {
        "changeme",
        "dummy",
        "example",
        "fake",
        "password",
        "placeholder",
        "redacted",
        "replace",
        "sample",
        "test",
        "your",
    }
)


@dataclass(frozen=True, order=True)
class Finding:
    rule: str
    relative_path: str
    line: int | None = None

    @property
    def path_digest(self) -> str:
        digest = hashlib.sha256(self.relative_path.encode("utf-8")).hexdigest()
        return digest[:12]

    def redacted(self) -> dict[str, object]:
        result: dict[str, object] = {
            "rule": self.rule,
            "path_digest": self.path_digest,
        }
        if self.line is not None:
            result["line"] = self.line
        return result


def _normalise_relative(path: Path, root: Path) -> str:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = Path(path.name)
    return relative.as_posix()


def _is_public_context(relative_path: str) -> bool:
    lowered = relative_path.lower()
    if relative_path in KNOWN_PUBLIC_FILES:
        return True
    if any(lowered.startswith(prefix) for prefix in ARCHITECTURE_PREFIXES):
        return True
    return any(part.lower() in SYNTHETIC_PATH_MARKERS for part in Path(relative_path).parts)


def _looks_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(word in lowered for word in PLACEHOLDER_WORDS) or "${" in value


def _line_number(text: str, start: int) -> int:
    return text.count("\n", 0, start) + 1


def _matches(pattern: re.Pattern[str], text: str) -> Iterator[re.Match[str]]:
    yield from pattern.finditer(text)


def _credential_findings(text: str, relative_path: str) -> Iterator[Finding]:
    patterns = (
        ("credential_private_key", PRIVATE_KEY),
        ("credential_aws_access_key", AWS_ACCESS_KEY),
        ("credential_github_token", GITHUB_TOKEN),
        ("credential_google_api_key", GOOGLE_API_KEY),
        ("credential_slack_token", SLACK_TOKEN),
        ("credential_bearer_token", BEARER_TOKEN),
    )
    for rule, pattern in patterns:
        for match in _matches(pattern, text):
            yield Finding(rule, relative_path, _line_number(text, match.start()))

    for match in _matches(AUTHORITY_CREDENTIAL, text):
        if not _looks_placeholder(match.group(1)):
            yield Finding(
                "credential_assignment",
                relative_path,
                _line_number(text, match.start()),
            )


def _content_findings(
    text: str, relative_path: str, *, public_context: bool
) -> Iterator[Finding]:
    yield from _credential_findings(text, relative_path)
    if public_context:
        return

    patterns = (
        ("private_windows_path", PRIVATE_WINDOWS_PATH),
        ("cloud_drive_id", DRIVE_URL),
        ("cloud_drive_id", DRIVE_ID_ASSIGNMENT),
        ("client_report_filename", REPORT_REFERENCE),
    )
    for rule, pattern in patterns:
        for match in _matches(pattern, text):
            yield Finding(rule, relative_path, _line_number(text, match.start()))


def _path_findings(path: Path, relative_path: str, *, public_context: bool) -> Iterator[Finding]:
    if public_context:
        return
    if (
        path.suffix.lower() in SENSITIVE_REPORT_SUFFIXES
        and SENSITIVE_REPORT_NAME.search(path.stem)
    ):
        yield Finding("client_report_filename", relative_path)


def _scan_file(path: Path, root: Path) -> list[Finding]:
    relative_path = _normalise_relative(path, root)
    public_context = _is_public_context(relative_path)
    findings = list(_path_findings(path, relative_path, public_context=public_context))

    if path.is_symlink():
        findings.append(Finding("unscannable_symlink", relative_path))
        return findings

    try:
        size = path.stat().st_size
    except OSError:
        findings.append(Finding("unreadable_file", relative_path))
        return findings

    if size > MAX_FILE_BYTES:
        findings.append(Finding("oversized_file", relative_path))
        return findings

    try:
        data = path.read_bytes()
    except OSError:
        findings.append(Finding("unreadable_file", relative_path))
        return findings

    if b"\x00" in data:
        return findings
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        # Binary/non-UTF-8 content is still checked by filename. Publication
        # review should separately validate binary provenance and metadata.
        return findings

    findings.extend(_content_findings(text, relative_path, public_context=public_context))
    return findings


def _iter_files(root: Path) -> Iterator[Path]:
    if root.is_file() or root.is_symlink():
        yield root
        return
    for directory, names, files in os.walk(root, topdown=True, followlinks=False):
        names[:] = sorted(name for name in names if name not in IGNORED_DIRECTORY_NAMES)
        base = Path(directory)
        for name in sorted(files):
            yield base / name


def scan_path(path: Path | str) -> list[Finding]:
    """Return deterministic findings for *path* without modifying it."""

    requested = Path(path).resolve()
    if not requested.exists() and not requested.is_symlink():
        return [Finding("missing_scan_root", requested.name or ".")]

    root = requested if requested.is_dir() else requested.parent
    findings: list[Finding] = []
    for candidate in _iter_files(requested):
        findings.extend(_scan_file(candidate, root))
    return sorted(set(findings))


def summarise(findings: Iterable[Finding]) -> dict[str, object]:
    materialised = sorted(set(findings))
    by_rule = Counter(finding.rule for finding in materialised)
    return {
        "pass": not materialised,
        "finding_count": len(materialised),
        "by_rule": dict(sorted(by_rule.items())),
        "findings": [finding.redacted() for finding in materialised],
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", help="file or tree to scan")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit a machine-readable redacted result",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result = summarise(scan_path(args.path))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        verdict = "PASS" if result["pass"] else "FAIL"
        print(f"PUBLICATION_POLICY={verdict}")
        print(f"FINDING_COUNT={result['finding_count']}")
        for rule, count in result["by_rule"].items():
            print(f"{rule}={count}")
        if result["findings"]:
            print("REDACTED_FINDINGS=" + json.dumps(result["findings"], sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
