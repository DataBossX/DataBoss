#!/usr/bin/env python3
"""Fail closed when tracked files violate the public-repository boundary."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping, Sequence


DEFAULT_CONFIG = Path("config/publication_policy.json")


@dataclass(frozen=True)
class Finding:
    path: str
    rule_id: str
    message: str
    redact_path: bool = False


CompiledRule = tuple[str, str, re.Pattern[str]]


def _compile_pattern(pattern: object, description: str) -> re.Pattern[str]:
    if not isinstance(pattern, str) or not pattern:
        raise ValueError(f"{description} must be a non-empty string")
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as error:
        raise ValueError(f"{description} is not a valid regular expression") from error


def _compile_rules(raw_rules: object, field: str) -> list[CompiledRule]:
    if not isinstance(raw_rules, list):
        raise ValueError(f"configuration field {field!r} must be a list")

    compiled_rules: list[CompiledRule] = []
    rule_ids: set[str] = set()
    for index, rule in enumerate(raw_rules):
        description = f"{field}[{index}]"
        if not isinstance(rule, dict):
            raise ValueError(f"{description} must be an object")

        rule_id = rule.get("id")
        message = rule.get("message")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError(f"{description}.id must be a non-empty string")
        if rule_id in rule_ids:
            raise ValueError(f"duplicate rule id {rule_id!r}")
        if not isinstance(message, str) or not message:
            raise ValueError(f"{description}.message must be a non-empty string")

        pattern = _compile_pattern(rule.get("pattern"), f"{description}.pattern")
        compiled_rules.append((rule_id, message, pattern))
        rule_ids.add(rule_id)

    return compiled_rules


def _tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [
        entry.decode("utf-8", errors="surrogateescape")
        for entry in result.stdout.split(b"\0")
        if entry
    ]


def _is_exempt(path: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    return any(pattern.search(path) for pattern in patterns)


def _normalize_path(raw_path: str) -> str:
    if not isinstance(raw_path, str):
        raise ValueError("paths must be strings")

    normalized_separators = raw_path.replace("\\", "/")
    path = PurePosixPath(normalized_separators)
    if path.is_absolute() or path == PurePosixPath(".") or ".." in path.parts:
        raise ValueError("path escapes the repository root")
    if re.match(r"^[A-Za-z]:/", normalized_separators):
        raise ValueError("path escapes the repository root")
    return path.as_posix()


def scan_paths(
    root: Path,
    paths: Iterable[str],
    config: Mapping[str, object],
) -> list[Finding]:
    """Return redacted findings without exposing matched source content."""
    path_rules = _compile_rules(
        config.get("forbidden_path_rules"), "forbidden_path_rules"
    )
    content_rules = _compile_rules(
        config.get("forbidden_content_rules"), "forbidden_content_rules"
    )

    raw_exemptions = config.get("content_exempt_paths", [])
    if not isinstance(raw_exemptions, list):
        raise ValueError("configuration field 'content_exempt_paths' must be a list")
    content_exemptions = [
        _compile_pattern(pattern, f"content_exempt_paths[{index}]")
        for index, pattern in enumerate(raw_exemptions)
    ]

    max_bytes = config.get("max_text_file_bytes", 2_000_000)
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_text_file_bytes must be a positive integer")

    resolved_root = root.resolve(strict=True)
    findings: list[Finding] = []

    for raw_path in sorted(set(paths)):
        try:
            normalized = _normalize_path(raw_path)
        except ValueError:
            findings.append(
                Finding(
                    str(raw_path),
                    "path_traversal",
                    "Path escapes the repository root.",
                    redact_path=True,
                )
            )
            continue

        path_is_forbidden = False
        for rule_id, message, pattern in path_rules:
            if pattern.search(normalized):
                findings.append(
                    Finding(normalized, rule_id, message, redact_path=True)
                )
                path_is_forbidden = True
        if path_is_forbidden:
            continue

        absolute = resolved_root / normalized
        if not absolute.exists():
            raise OSError(f"cannot scan missing file {normalized!r}")
        if absolute.is_symlink():
            raise OSError(f"refusing to follow symbolic link {normalized!r}")
        if absolute.resolve(strict=True) != absolute:
            raise OSError(f"refusing to follow symbolic link in {normalized!r}")
        if not absolute.is_file():
            raise OSError(f"cannot scan non-file path {normalized!r}")

        if absolute.stat().st_size > max_bytes:
            raise OSError(
                f"file {normalized!r} exceeds the {max_bytes}-byte scan limit"
            )
        if _is_exempt(normalized, content_exemptions):
            continue

        with absolute.open("rb") as stream:
            data = stream.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise OSError(
                f"file {normalized!r} changed while being scanned or exceeds "
                f"the {max_bytes}-byte scan limit"
            )
        if not data:
            continue
        content = data.decode("utf-8", errors="ignore")

        for rule_id, message, pattern in content_rules:
            if pattern.search(content):
                findings.append(Finding(normalized, rule_id, message))

    return findings


def load_config(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as stream:
        config = json.load(stream)
    if not isinstance(config, dict):
        raise ValueError("configuration root must be an object")

    _compile_rules(config.get("forbidden_path_rules"), "forbidden_path_rules")
    _compile_rules(config.get("forbidden_content_rules"), "forbidden_content_rules")
    return config


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "paths",
        nargs="*",
        help="Repository-relative paths; defaults to every Git-tracked file.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    root = args.root.resolve()
    config_path = args.config
    if not config_path.is_absolute():
        config_path = root / config_path

    try:
        config = load_config(config_path)
        paths = args.paths or _tracked_files(root)
        findings = scan_paths(root, paths, config)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"publication-policy check failed safely: {error}", file=sys.stderr)
        return 2

    if findings:
        print("Publication-policy violations:")
        for finding in findings:
            path = (
                "<redacted path>"
                if finding.redact_path
                else json.dumps(finding.path, ensure_ascii=True)
            )
            print(f"- {path}: [{finding.rule_id}] {finding.message}")
        print("Matched values are intentionally redacted.")
        return 1

    print(f"Publication-policy check passed ({len(paths)} files scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
