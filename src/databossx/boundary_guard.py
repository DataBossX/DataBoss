"""Public-boundary guard: fail when private title work product reaches a public tree.

Implements the publication gate in docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md
as an allowlist-first check:

* Office, PDF, archive, and database files are only allowed in approved
  public-asset locations (``config/boundary_guard.json``).
* Text files are scanned for Wyoming-style federal serials, township/range/section
  strings, cloud file and folder links, private Windows paths, and SHA-256 evidence
  hashes. Project and client identifiers are not hard-coded here, because naming
  them in a public file would leak them. Supply them privately through
  ``BOUNDARY_GUARD_EXTRA_PATTERNS`` (JSON list of regexes, e.g. a CI secret) or
  the git-ignored ``.boundary-guard.local.json``.

Findings never echo the matched value, so logs stay safe to share.
Standard library only.

    python -m databossx.boundary_guard --base origin/main      # CI: files changed on a branch
    python -m databossx.boundary_guard --staged                # pre-commit
    python -m databossx.boundary_guard --all                   # whole tracked tree
    python -m databossx.boundary_guard path/to/file ...        # explicit files
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence

ERROR = "error"
WARN = "warn"

# Files that are opaque to a text scan and routinely carry client work product.
BLOCKED_EXTENSIONS = frozenset(
    {
        ".xlsx", ".xlsm", ".xls", ".ods", ".csv", ".tsv",
        ".docx", ".doc", ".odt", ".rtf",
        ".pdf", ".tif", ".tiff",
        ".zip", ".7z", ".rar", ".tar", ".gz", ".tgz",
        ".db", ".sqlite", ".sqlite3",
    }
)
# Raster images are only blocked outside the allowlist too (scanned instruments).
BLOCKED_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"})

BLOCKED_DIR_NAMES = frozenset({"deliverables", "evidence", "turn_in", "turnin", "qa_internal"})

TEXT_EXTENSIONS = frozenset(
    {
        ".py", ".md", ".txt", ".json", ".toml", ".yml", ".yaml", ".sql", ".js", ".mjs",
        ".ts", ".tsx", ".jsx", ".html", ".css", ".astro", ".bat", ".ps1", ".sh", ".ini",
        ".cfg", ".env", ".xml", ".svg",
    }
)

# Directories whose contents are never scanned (dependencies, VCS data).
SKIP_DIR_NAMES = frozenset({".git", "node_modules", ".venv", "venv", "__pycache__", "dist"})
SKIP_FILE_NAMES = frozenset({"package-lock.json", "yarn.lock", "pnpm-lock.yaml"})

MAX_SCAN_BYTES = 2_000_000


@dataclass(frozen=True)
class Rule:
    code: str
    severity: str
    pattern: re.Pattern[str]
    message: str


def _rx(expr: str, flags: int = 0) -> re.Pattern[str]:
    return re.compile(expr, flags)


BUILTIN_RULES: tuple[Rule, ...] = (
    Rule("federal-serial", ERROR, _rx(r"\bWYWY?[- ]?\d{5,9}X?\b", re.I),
         "federal lease or MLRS serial"),
    Rule("legacy-federal-serial", ERROR, _rx(r"\bUSA\s+[A-Z]-\d{4,6}\b"),
         "legacy federal serial"),
    Rule("section-township-range", ERROR, _rx(r"\b\d{1,2}-\d{1,3}N-\d{1,3}[EW]\b", re.I),
         "section-township-range legal reference"),
    Rule("township-range", ERROR, _rx(r"\bT\s?\d{1,3}\s?N[,\s-]*R\s?\d{1,3}\s?[EW]\b", re.I),
         "township and range reference"),
    Rule("cloud-file-link", ERROR,
         _rx(r"(?:drive|docs)\.google\.com/(?:file/d|drive/folders|document/d|spreadsheets/d|presentation/d)/[A-Za-z0-9_-]{20,}"),
         "cloud file or folder link"),
    Rule("cloud-file-id", ERROR, _rx(r"\b(?:fileId|folderId|file_id|folder_id)\W{1,4}[A-Za-z0-9_-]{25,}\b", re.I),
         "cloud file or folder identifier"),
    Rule("private-path", ERROR, _rx(r"\b[A-Z]:\\+(?:DataBoss\\+Penterra|Users\\+[^\\\s]+\\+(?:Desktop|Documents|Downloads))", re.I),
         "private Windows path"),
    Rule("data-root-path", WARN, _rx(r"\b[A-Z]:\\+DataBoss\b", re.I),
         "documented data-root path; confirm it names no client folder"),
    Rule("evidence-hash", WARN, _rx(r"\b[a-f0-9]{64}\b", re.I),
         "64-hex value that may be a source or evidence hash"),
)

# A line carrying this marker is skipped by every rule. Use only for reviewed, synthetic content.
INLINE_ALLOW = "boundary-guard: allow"


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    code: str
    severity: str
    message: str

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else self.path
        return f"{self.severity.upper():5} {where}: {self.code} - {self.message}"


@dataclass(frozen=True)
class Config:
    allow_binary_globs: tuple[str, ...]
    allow_scan_globs: tuple[str, ...]
    ignore_globs: tuple[str, ...]
    extra_rules: tuple[Rule, ...]
    # Exact, already-public fictional strings (case-insensitive) that the rules must not flag.
    synthetic_values: frozenset[str] = frozenset()


def _glob_match(rel: str, patterns: Iterable[str]) -> bool:
    posix = PurePosixPath(rel).as_posix()
    for pattern in patterns:
        if fnmatch.fnmatchcase(posix, pattern):
            return True
        if pattern.endswith("/**") and (posix == pattern[:-3] or posix.startswith(pattern[:-2])):
            return True
    return False


def _extra_rules(raw: object, source: str) -> list[Rule]:
    if not isinstance(raw, list):
        raise ValueError(f"{source}: expected a JSON list of regex strings")
    rules = []
    for index, expr in enumerate(raw):
        if not isinstance(expr, str) or not expr:
            raise ValueError(f"{source}: item {index} is not a non-empty string")
        rules.append(Rule(f"private-identifier-{index + 1}", ERROR, re.compile(expr, re.I),
                          "private project or client identifier"))
    return rules


def load_config(root: Path, env: dict[str, str] | None = None) -> Config:
    env = os.environ if env is None else env
    allow_binary: list[str] = []
    allow_scan: list[str] = []
    ignore: list[str] = []
    synthetic: frozenset[str] = frozenset()
    config_path = root / "config" / "boundary_guard.json"
    if config_path.is_file():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        allow_binary = list(data.get("allow_binary_globs", []))
        allow_scan = list(data.get("allow_scan_globs", []))
        ignore = list(data.get("ignore_globs", []))
        synthetic = frozenset(str(v).lower() for v in data.get("synthetic_values", []))
    extras: list[Rule] = []
    local_path = root / ".boundary-guard.local.json"
    if local_path.is_file():
        extras += _extra_rules(json.loads(local_path.read_text(encoding="utf-8")), str(local_path.name))
    raw_env = env.get("BOUNDARY_GUARD_EXTRA_PATTERNS", "").strip()
    if raw_env:
        extras += _extra_rules(json.loads(raw_env), "BOUNDARY_GUARD_EXTRA_PATTERNS")
    return Config(tuple(allow_binary), tuple(allow_scan), tuple(ignore), tuple(extras), synthetic)


def _is_binary(data: bytes) -> bool:
    return b"\x00" in data[:4096]


def check_path_rules(rel: str, config: Config) -> list[Finding]:
    """Path-only checks: blocked extensions and blocked directory names."""
    findings: list[Finding] = []
    pure = PurePosixPath(rel)
    suffix = pure.suffix.lower()
    parts = {part.lower() for part in pure.parts[:-1]}
    allowed = _glob_match(rel, config.allow_binary_globs)
    if suffix in BLOCKED_EXTENSIONS and not allowed:
        findings.append(Finding(rel, 0, "blocked-file-type", ERROR,
                                f"{suffix} files may carry client work product; allow only under an approved public-asset path"))
    elif suffix in BLOCKED_IMAGE_EXTENSIONS and not allowed:
        findings.append(Finding(rel, 0, "image-outside-allowlist", ERROR,
                                "image outside approved public-asset paths may be a scanned source instrument"))
    hit = parts & BLOCKED_DIR_NAMES
    if hit and not allowed:
        findings.append(Finding(rel, 0, "blocked-directory", ERROR,
                                f"directory name '{sorted(hit)[0]}' is reserved for private work product"))
    return findings


def scan_text(rel: str, text: str, rules: Sequence[Rule], synthetic: frozenset[str] = frozenset()) -> list[Finding]:
    findings: list[Finding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if INLINE_ALLOW in line:
            continue
        for rule in rules:
            if any(m.group(0).lower() not in synthetic for m in rule.pattern.finditer(line)):
                findings.append(Finding(rel, number, rule.code, rule.severity, rule.message))
    return findings


def scan_file(root: Path, rel: str, config: Config) -> list[Finding]:
    if _glob_match(rel, config.ignore_globs):
        return []
    pure = PurePosixPath(rel)
    if set(pure.parts) & SKIP_DIR_NAMES or pure.name in SKIP_FILE_NAMES:
        return []
    findings = check_path_rules(rel, config)
    full = root / rel
    if not full.is_file():
        return findings
    suffix = pure.suffix.lower()
    if suffix not in TEXT_EXTENSIONS and pure.name not in {".gitignore", ".env.example", "Dockerfile"}:
        return findings
    if _glob_match(rel, config.allow_scan_globs):
        return findings
    try:
        data = full.read_bytes()[:MAX_SCAN_BYTES]
    except OSError as exc:
        findings.append(Finding(rel, 0, "unreadable", ERROR, f"cannot read file: {exc.__class__.__name__}"))
        return findings
    if _is_binary(data):
        return findings
    rules = list(BUILTIN_RULES) + list(config.extra_rules)
    findings += scan_text(rel, data.decode("utf-8", errors="replace"), rules, config.synthetic_values)
    return findings


def _git(root: Path, *args: str) -> list[str]:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
    return [line for line in result.stdout.splitlines() if line]


def changed_files(root: Path, base: str) -> list[str]:
    return _git(root, "diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD")


def staged_files(root: Path) -> list[str]:
    return _git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR")


def tracked_files(root: Path) -> list[str]:
    return _git(root, "ls-files")


def run(root: Path, files: Sequence[str], config: Config) -> list[Finding]:
    findings: list[Finding] = []
    for rel in sorted(set(files)):
        findings += scan_file(root, rel, config)
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Block private title work product from public repositories.")
    parser.add_argument("files", nargs="*", help="explicit files, relative to --root")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--base", help="check files changed since this ref (CI)")
    group.add_argument("--staged", action="store_true", help="check staged files (pre-commit)")
    group.add_argument("--all", action="store_true", help="check every tracked file")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    config = load_config(root)
    if args.base:
        files = changed_files(root, args.base)
    elif args.staged:
        files = staged_files(root)
    elif args.all:
        files = tracked_files(root)
    else:
        files = list(args.files)
    if not files:
        print("boundary-guard: nothing to check.")
        return 0

    findings = run(root, files, config)
    errors = [f for f in findings if f.severity == ERROR or (args.strict and f.severity == WARN)]
    for finding in findings:
        print(finding)
    if errors:
        print(
            f"boundary-guard: {len(errors)} blocking finding(s) in {len({f.path for f in errors})} file(s). "
            "Keep real title work product in the private workspace. Matched values are intentionally not printed.",
            file=sys.stderr,
        )
        return 1
    print(f"boundary-guard: {len(files)} file(s) checked, {len(findings)} warning(s), 0 blocking.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
