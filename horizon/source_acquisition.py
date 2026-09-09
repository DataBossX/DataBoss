"""Read-only acquisition inventory for section abstract source roots.

This module never copies, deletes, renames, or selects an authoritative file.
It hashes mounted source roots and reports conflicts that must be resolved
before extraction or workbook mutation begins.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA_ID = "dbx.source_acquisition_receipt"
SCHEMA_VERSION = "1.0"
PRIORITY_SECTIONS = (15, 13, 11)
DEFAULT_REQUIRED_ROLES = ("source_document", "master_workbook", "index")
SOURCE_ROLES = {
    "chat_export",
    "handwritten_index",
    "index",
    "master_workbook",
    "ocr_text",
    "source_document",
    "supporting_record",
    "workbook",
}
SUPPORTED_EXTENSIONS = {
    ".csv",
    ".doc",
    ".docx",
    ".json",
    ".jpeg",
    ".jpg",
    ".md",
    ".pdf",
    ".png",
    ".tif",
    ".tiff",
    ".txt",
    ".xls",
    ".xlsm",
    ".xlsx",
}
WORKBOOK_EXTENSIONS = {".xls", ".xlsm", ".xlsx"}
IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".tif", ".tiff"}
SOURCE_DOCUMENT_EXTENSIONS = {".doc", ".docx", ".pdf", *IMAGE_EXTENSIONS}
_SECTION_PATTERN = re.compile(
    r"(?i)(?:^|[^a-z0-9])sec(?:tion)?[\s_-]*0?(11|13|15)(?![a-z0-9])"
)
_TOWNSHIP_SECTION_PATTERN = re.compile(
    r"(?i)(?:^|[/\\])0?(11|13|15)-\d{1,2}[ns]-\d{1,3}[ew](?:[/\\]|$)"
)
_HIDDEN_PARTS = {".git", ".svn", "__pycache__", ".pytest_cache"}
_ROLE_EQUIVALENTS = {
    "index": {"index", "handwritten_index"},
}


class SourceAcquisitionError(ValueError):
    """Raised when source acquisition controls are unsafe or malformed."""


@dataclass(frozen=True)
class SourceRoot:
    label: str
    path: Path


@dataclass(frozen=True)
class SourceFile:
    root_label: str
    relative_path: str
    section: int
    role: str
    extension: str
    size_bytes: int
    modified_utc: str
    sha256: str


@dataclass(frozen=True)
class SourceIssue:
    code: str
    message: str
    root_label: str = ""
    relative_path: str = ""
    section: Optional[int] = None


@dataclass(frozen=True)
class PathComparison:
    section: int
    relative_path: str
    status: str
    roots: Tuple[str, ...]
    sha256_values: Tuple[str, ...]


@dataclass
class SectionSummary:
    section: int
    file_count: int
    roots_present: List[str]
    role_counts: Dict[str, int]
    missing_required_roles: List[str]
    conflicting_paths: int
    issue_count: int
    ready_for_extraction: bool


@dataclass
class AcquisitionReceipt:
    generated_utc: str
    roots: Dict[str, str]
    requested_sections: List[int]
    required_roles: List[str]
    files: List[SourceFile]
    path_comparisons: List[PathComparison]
    duplicate_content: List[Dict[str, object]]
    issues: List[SourceIssue]
    sections: List[SectionSummary]
    technical_pass: bool
    schema_id: str = SCHEMA_ID
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_section(relative_path: str) -> Optional[int]:
    """Return a prioritized section only when the path explicitly names it."""
    match = _SECTION_PATTERN.search(relative_path)
    if match is None:
        match = _TOWNSHIP_SECTION_PATTERN.search(relative_path)
    return int(match.group(1)) if match else None


def classify_role(relative_path: str, extension: str) -> str:
    normalized = relative_path.casefold().replace("\\", "/")
    stem = Path(normalized).stem
    if any(token in normalized for token in ("chat", "slack", "transcript")):
        return "chat_export"
    if any(token in normalized for token in ("/ocr/", "ocr_", "_ocr", "extracted_text")):
        return "ocr_text"
    if "index" in normalized and (
        "handwritten" in normalized
        or "hand_written" in normalized
        or "hand-written" in normalized
    ):
        return "handwritten_index"
    if "index" in normalized:
        return "index"
    if extension in WORKBOOK_EXTENSIONS and any(
        token in stem for token in ("master", "report", "runsheet")
    ):
        return "master_workbook"
    if extension in SOURCE_DOCUMENT_EXTENSIONS:
        return "source_document"
    if extension in WORKBOOK_EXTENSIONS:
        return "workbook"
    return "supporting_record"


def _is_ignored(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    return any(
        part in _HIDDEN_PARTS
        or part.startswith(".")
        or part.startswith("~$")
        for part in relative_parts
    )


def _iter_source_paths(root: Path) -> Iterable[Path]:
    for directory, names, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        names[:] = sorted(
            name
            for name in names
            if not _is_ignored(directory_path / name, root)
        )
        for filename in sorted(filenames):
            path = directory_path / filename
            if not _is_ignored(path, root):
                yield path


def validate_roots(roots: Sequence[SourceRoot]) -> List[SourceRoot]:
    if not roots:
        raise SourceAcquisitionError("At least one source root is required")
    labels = [root.label for root in roots]
    if any(not label or not re.fullmatch(r"[a-z][a-z0-9_-]*", label) for label in labels):
        raise SourceAcquisitionError(
            "Root labels must use lowercase letters, numbers, underscores, or hyphens"
        )
    if len(labels) != len(set(labels)):
        raise SourceAcquisitionError("Source root labels must be unique")

    validated: List[SourceRoot] = []
    resolved_paths: List[Path] = []
    for root in roots:
        resolved = root.path.expanduser().resolve()
        if not resolved.is_dir():
            raise SourceAcquisitionError(
                f"Source root {root.label!r} is not a directory: {resolved}"
            )
        if any(
            resolved == existing
            or resolved.is_relative_to(existing)
            or existing.is_relative_to(resolved)
            for existing in resolved_paths
        ):
            raise SourceAcquisitionError(
                "Source roots must be unique and must not overlap"
            )
        resolved_paths.append(resolved)
        validated.append(SourceRoot(root.label, resolved))
    return validated


def inventory_roots(
    roots: Sequence[SourceRoot],
    requested_sections: Sequence[int] = PRIORITY_SECTIONS,
) -> Tuple[List[SourceFile], List[SourceIssue]]:
    requested = set(requested_sections)
    files: List[SourceFile] = []
    issues: List[SourceIssue] = []
    for root in validate_roots(roots):
        for path in _iter_source_paths(root.path):
            relative = path.relative_to(root.path).as_posix()
            section = detect_section(relative)
            if section not in requested:
                continue
            if path.is_symlink():
                issues.append(
                    SourceIssue(
                        code="source_symlink_rejected",
                        message="Symlinked source files are not accepted as authority",
                        root_label=root.label,
                        relative_path=relative,
                        section=section,
                    )
                )
                continue
            extension = path.suffix.casefold()
            if extension not in SUPPORTED_EXTENSIONS:
                continue
            try:
                before = path.stat()
                digest = sha256_file(path)
                after = path.stat()
            except OSError as exc:
                issues.append(
                    SourceIssue(
                        code="source_read_failed",
                        message=str(exc),
                        root_label=root.label,
                        relative_path=relative,
                        section=section,
                    )
                )
                continue
            if before.st_size == 0:
                issues.append(
                    SourceIssue(
                        code="source_empty",
                        message="Zero-byte files are not accepted as source evidence",
                        root_label=root.label,
                        relative_path=relative,
                        section=section,
                    )
                )
                continue
            if (
                before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
                or before.st_ino != after.st_ino
            ):
                issues.append(
                    SourceIssue(
                        code="source_changed_during_hash",
                        message="Source changed while its acquisition hash was computed",
                        root_label=root.label,
                        relative_path=relative,
                        section=section,
                    )
                )
                continue
            files.append(
                SourceFile(
                    root_label=root.label,
                    relative_path=relative,
                    section=section,
                    role=classify_role(relative, extension),
                    extension=extension,
                    size_bytes=after.st_size,
                    modified_utc=datetime.fromtimestamp(
                        after.st_mtime, timezone.utc
                    ).isoformat(),
                    sha256=digest,
                )
            )
    return sorted(
        files,
        key=lambda item: (
            PRIORITY_SECTIONS.index(item.section),
            item.relative_path.casefold(),
            item.root_label,
        ),
    ), issues


def compare_paths(files: Sequence[SourceFile]) -> List[PathComparison]:
    grouped: Dict[Tuple[int, str], List[SourceFile]] = defaultdict(list)
    for item in files:
        grouped[(item.section, item.relative_path.casefold())].append(item)

    comparisons: List[PathComparison] = []
    for (section, relative_key), group in sorted(grouped.items()):
        roots = tuple(sorted(item.root_label for item in group))
        hashes = tuple(sorted({item.sha256 for item in group}))
        if len(group) == 1:
            status = "single_root"
        elif len(hashes) == 1:
            status = "exact_match"
        else:
            status = "hash_conflict"
        display_path = min(item.relative_path for item in group)
        comparisons.append(
            PathComparison(
                section=section,
                relative_path=display_path,
                status=status,
                roots=roots,
                sha256_values=hashes,
            )
        )
    return comparisons


def duplicate_content_groups(files: Sequence[SourceFile]) -> List[Dict[str, object]]:
    grouped: Dict[str, List[SourceFile]] = defaultdict(list)
    for item in files:
        grouped[item.sha256].append(item)
    groups: List[Dict[str, object]] = []
    for digest, matches in sorted(grouped.items()):
        unique_locations = sorted(
            {f"{item.root_label}:{item.relative_path}" for item in matches}
        )
        if len(unique_locations) > 1:
            groups.append({"sha256": digest, "locations": unique_locations})
    return groups


def _summarize_section(
    section: int,
    files: Sequence[SourceFile],
    comparisons: Sequence[PathComparison],
    issues: Sequence[SourceIssue],
    required_roles: Sequence[str],
) -> SectionSummary:
    section_files = [item for item in files if item.section == section]
    role_counts = Counter(item.role for item in section_files)
    missing_roles = [
        role
        for role in required_roles
        if not any(
            role_counts[candidate]
            for candidate in _ROLE_EQUIVALENTS.get(role, {role})
        )
    ]
    conflict_count = sum(
        comparison.status == "hash_conflict"
        for comparison in comparisons
        if comparison.section == section
    )
    issue_count = sum(issue.section == section for issue in issues)
    ready = (
        bool(section_files)
        and not missing_roles
        and conflict_count == 0
        and issue_count == 0
    )
    return SectionSummary(
        section=section,
        file_count=len(section_files),
        roots_present=sorted({item.root_label for item in section_files}),
        role_counts=dict(sorted(role_counts.items())),
        missing_required_roles=missing_roles,
        conflicting_paths=conflict_count,
        issue_count=issue_count,
        ready_for_extraction=ready,
    )


def build_receipt(
    roots: Sequence[SourceRoot],
    *,
    requested_sections: Sequence[int] = PRIORITY_SECTIONS,
    required_roles: Sequence[str] = DEFAULT_REQUIRED_ROLES,
) -> AcquisitionReceipt:
    if not requested_sections or any(
        type(section) is not int or section not in PRIORITY_SECTIONS
        for section in requested_sections
    ):
        raise SourceAcquisitionError(
            f"Requested sections must come from {PRIORITY_SECTIONS}"
        )
    if len(requested_sections) != len(set(requested_sections)):
        raise SourceAcquisitionError("Requested sections must be unique")
    if not required_roles or any(
        not isinstance(role, str)
        or role not in SOURCE_ROLES
        for role in required_roles
    ):
        raise SourceAcquisitionError(
            f"Required roles must come from {sorted(SOURCE_ROLES)}"
        )
    if len(required_roles) != len(set(required_roles)):
        raise SourceAcquisitionError("Required roles must be unique")

    validated_roots = validate_roots(roots)
    files, issues = inventory_roots(validated_roots, requested_sections)
    comparisons = compare_paths(files)
    summaries = [
        _summarize_section(
            section,
            files,
            comparisons,
            issues,
            required_roles,
        )
        for section in requested_sections
    ]
    return AcquisitionReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        roots={root.label: str(root.path) for root in validated_roots},
        requested_sections=list(requested_sections),
        required_roles=list(required_roles),
        files=files,
        path_comparisons=comparisons,
        duplicate_content=duplicate_content_groups(files),
        issues=issues,
        sections=summaries,
        technical_pass=all(summary.ready_for_extraction for summary in summaries),
    )


def write_receipt(receipt: AcquisitionReceipt, output_path: Path) -> None:
    output = output_path.expanduser().resolve()
    for source_root in receipt.roots.values():
        try:
            output.relative_to(Path(source_root))
        except ValueError:
            continue
        raise SourceAcquisitionError(
            "Receipt output must be outside every read-only source root"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(
        json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(output)


def parse_root(value: str) -> SourceRoot:
    label, separator, path = value.partition("=")
    if not separator or not path:
        raise argparse.ArgumentTypeError("Roots must use LABEL=/absolute/or/local/path")
    return SourceRoot(label.strip(), Path(path.strip()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hash and reconcile read-only section source roots"
    )
    parser.add_argument(
        "--root",
        action="append",
        type=parse_root,
        required=True,
        help="Repeatable source root, for example pc=D:/DataBoss or drive=G:/My Drive",
    )
    parser.add_argument(
        "--section",
        action="append",
        type=int,
        choices=PRIORITY_SECTIONS,
        dest="sections",
        help="Repeat to override the default priority set: 15, 13, 11",
    )
    parser.add_argument(
        "--require-role",
        action="append",
        dest="required_roles",
        help="Repeat to override required source roles",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = build_receipt(
            args.root,
            requested_sections=args.sections or PRIORITY_SECTIONS,
            required_roles=args.required_roles or DEFAULT_REQUIRED_ROLES,
        )
        write_receipt(receipt, args.output)
    except SourceAcquisitionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "technical_pass": receipt.technical_pass,
                "sections": [
                    {
                        "section": summary.section,
                        "ready_for_extraction": summary.ready_for_extraction,
                        "missing_required_roles": summary.missing_required_roles,
                        "conflicting_paths": summary.conflicting_paths,
                    }
                    for summary in receipt.sections
                ],
            },
            indent=2,
        )
    )
    return 0 if receipt.technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
