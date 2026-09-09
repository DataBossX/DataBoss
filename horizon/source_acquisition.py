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
import stat
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

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
    candidate_role: str
    extension: str
    size_bytes: int
    modified_utc: str
    modified_ns: int
    device: int
    inode: int
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


@dataclass(frozen=True)
class AuthorityAssertion:
    root_label: str
    relative_path: str
    section: int
    role: str
    expected_sha256: str


@dataclass(frozen=True)
class AuthorityMatch:
    assertion: AuthorityAssertion
    status: str


@dataclass
class SectionSummary:
    section: int
    file_count: int
    roots_present: List[str]
    candidate_role_counts: Dict[str, int]
    authorized_role_counts: Dict[str, int]
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
    authority_matches: List[AuthorityMatch]
    issues: List[SourceIssue]
    sections: List[SectionSummary]
    technical_pass: bool
    schema_id: str = SCHEMA_ID
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _hash_regular_file(
    path: Path,
    chunk_size: int = 1024 * 1024,
) -> Tuple[str, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    digest = hashlib.sha256()
    with os.fdopen(descriptor, "rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise SourceAcquisitionError(f"Source is not a regular file: {path}")
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
        after = os.fstat(handle.fileno())
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ino != after.st_ino
        or before.st_dev != after.st_dev
    ):
        raise SourceAcquisitionError(f"Source changed while hashing: {path}")
    linked = path.lstat()
    if stat.S_ISLNK(linked.st_mode) or (
        linked.st_ino != after.st_ino or linked.st_dev != after.st_dev
    ):
        raise SourceAcquisitionError(f"Source link changed while hashing: {path}")
    return digest.hexdigest(), after


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest, _ = _hash_regular_file(path, chunk_size)
    return digest


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


def _iter_source_paths(
    root: SourceRoot,
    issues: List[SourceIssue],
) -> Iterable[Path]:
    def record_traversal_error(error: OSError) -> None:
        failed_path = Path(error.filename) if error.filename else root.path
        try:
            relative = failed_path.relative_to(root.path).as_posix()
        except ValueError:
            relative = ""
        issues.append(
            SourceIssue(
                code="source_traversal_failed",
                message=str(error),
                root_label=root.label,
                relative_path=relative,
                section=detect_section(relative),
            )
        )

    for directory, names, filenames in os.walk(
        root.path,
        followlinks=False,
        onerror=record_traversal_error,
    ):
        directory_path = Path(directory)
        safe_directories = []
        for name in sorted(names):
            path = directory_path / name
            if _is_ignored(path, root.path):
                continue
            if path.is_symlink():
                relative = path.relative_to(root.path).as_posix()
                issues.append(
                    SourceIssue(
                        code="source_directory_symlink_rejected",
                        message="Symlinked source directories are not traversed",
                        root_label=root.label,
                        relative_path=relative,
                        section=detect_section(relative),
                    )
                )
                continue
            safe_directories.append(name)
        names[:] = safe_directories
        for filename in sorted(filenames):
            path = directory_path / filename
            if not _is_ignored(path, root.path):
                yield path


def validate_roots(roots: Sequence[SourceRoot]) -> List[SourceRoot]:
    if not roots:
        raise SourceAcquisitionError("At least one source root is required")
    labels = [root.label for root in roots]
    if any(
        not re.fullmatch(r"(?:pc|drive|chat)(?:[_-][a-z0-9]+)*", label)
        for label in labels
    ):
        raise SourceAcquisitionError(
            "Root labels must identify pc, drive, or chat sources"
        )
    if len(labels) != len(set(labels)):
        raise SourceAcquisitionError("Source root labels must be unique")

    validated: List[SourceRoot] = []
    resolved_paths: List[Path] = []
    for root in roots:
        expanded = root.path.expanduser()
        if not expanded.is_absolute():
            raise SourceAcquisitionError("Source roots must be absolute paths")
        resolved = expanded.resolve()
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
        for path in _iter_source_paths(root, issues):
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
                digest, source_stat = _hash_regular_file(path)
            except (OSError, SourceAcquisitionError) as exc:
                issues.append(
                    SourceIssue(
                        code=(
                            "source_link_or_race_rejected"
                            if path.is_symlink()
                            or "changed" in str(exc).casefold()
                            else "source_read_failed"
                        ),
                        message=str(exc),
                        root_label=root.label,
                        relative_path=relative,
                        section=section,
                    )
                )
                continue
            if source_stat.st_size == 0:
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
            files.append(
                SourceFile(
                    root_label=root.label,
                    relative_path=relative,
                    section=section,
                    candidate_role=classify_role(relative, extension),
                    extension=extension,
                    size_bytes=source_stat.st_size,
                    modified_utc=datetime.fromtimestamp(
                        source_stat.st_mtime, timezone.utc
                    ).isoformat(),
                    modified_ns=source_stat.st_mtime_ns,
                    device=source_stat.st_dev,
                    inode=source_stat.st_ino,
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


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def load_authority_manifest(path: Path) -> List[AuthorityAssertion]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceAcquisitionError(
            f"Cannot read authority manifest {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict) or set(payload) != {
        "schema_id",
        "schema_version",
        "authorities",
    }:
        raise SourceAcquisitionError("Authority manifest has invalid top-level fields")
    if (
        payload["schema_id"] != "dbx.source_authority_manifest"
        or payload["schema_version"] != "1.0"
        or not isinstance(payload["authorities"], list)
    ):
        raise SourceAcquisitionError("Authority manifest schema is invalid")

    assertions: List[AuthorityAssertion] = []
    seen = set()
    expected_fields = {
        "root_label",
        "relative_path",
        "section",
        "role",
        "expected_sha256",
    }
    for index, raw in enumerate(payload["authorities"]):
        if not isinstance(raw, dict) or set(raw) != expected_fields:
            raise SourceAcquisitionError(
                f"Authority assertion {index} has invalid fields"
            )
        root_label = raw["root_label"]
        relative_path = raw["relative_path"]
        section = raw["section"]
        role = raw["role"]
        digest = raw["expected_sha256"]
        relative = (
            PurePosixPath(relative_path)
            if isinstance(relative_path, str)
            else PurePosixPath()
        )
        if (
            not isinstance(root_label, str)
            or not isinstance(relative_path, str)
            or not relative_path
            or relative.is_absolute()
            or ".." in relative.parts
            or str(relative) != relative_path
            or type(section) is not int
            or section not in PRIORITY_SECTIONS
            or not isinstance(role, str)
            or role not in SOURCE_ROLES
            or not isinstance(digest, str)
            or not _is_sha256(digest.casefold())
        ):
            raise SourceAcquisitionError(
                f"Authority assertion {index} is invalid"
            )
        key = (root_label, relative_path, role)
        if key in seen:
            raise SourceAcquisitionError(
                f"Authority assertion {index} is duplicated"
            )
        seen.add(key)
        assertions.append(
            AuthorityAssertion(
                root_label=root_label,
                relative_path=relative_path,
                section=section,
                role=role,
                expected_sha256=digest.casefold(),
            )
        )
    return assertions


def _match_authorities(
    assertions: Sequence[AuthorityAssertion],
    files: Sequence[SourceFile],
    roots: Sequence[SourceRoot],
    requested_sections: Sequence[int],
    invalid_locations: set[Tuple[str, str]],
    issues: List[SourceIssue],
) -> List[AuthorityMatch]:
    root_labels = {root.label for root in roots}
    requested = set(requested_sections)
    file_index = {
        (item.root_label, item.relative_path): item
        for item in files
    }
    matches: List[AuthorityMatch] = []
    seen = set()
    for assertion in assertions:
        if (
            not isinstance(assertion.root_label, str)
            or not isinstance(assertion.relative_path, str)
            or not isinstance(assertion.role, str)
            or not isinstance(assertion.expected_sha256, str)
        ):
            raise SourceAcquisitionError("Authority assertion is invalid")
        relative = PurePosixPath(assertion.relative_path)
        if (
            not assertion.root_label
            or not assertion.relative_path
            or relative.is_absolute()
            or ".." in relative.parts
            or str(relative) != assertion.relative_path
            or type(assertion.section) is not int
            or assertion.section not in PRIORITY_SECTIONS
            or assertion.role not in SOURCE_ROLES
            or not _is_sha256(assertion.expected_sha256)
        ):
            raise SourceAcquisitionError("Authority assertion is invalid")
        key = (
            assertion.root_label,
            assertion.relative_path,
            assertion.role,
        )
        if key in seen:
            raise SourceAcquisitionError("Authority assertions must be unique")
        seen.add(key)
        if assertion.root_label not in root_labels:
            raise SourceAcquisitionError(
                f"Authority references unknown root {assertion.root_label!r}"
            )
        if assertion.section not in requested:
            raise SourceAcquisitionError(
                f"Authority references unrequested section {assertion.section}"
            )
        location = (assertion.root_label, assertion.relative_path)
        source = file_index.get(location)
        if location in invalid_locations:
            status = "source_unstable"
            code = "authority_source_unstable"
        elif source is None or source.section != assertion.section:
            status = "file_missing"
            code = "authority_file_missing"
        elif source.sha256 != assertion.expected_sha256:
            status = "hash_mismatch"
            code = "authority_hash_mismatch"
        else:
            status = "matched"
            code = ""
        matches.append(AuthorityMatch(assertion=assertion, status=status))
        if code:
            issues.append(
                SourceIssue(
                    code=code,
                    message=(
                        f"Authority {assertion.role!r} did not match "
                        f"{assertion.root_label}:{assertion.relative_path}"
                    ),
                    root_label=assertion.root_label,
                    relative_path=assertion.relative_path,
                    section=assertion.section,
                )
            )
    return matches


def _revalidate_inventory(
    files: Sequence[SourceFile],
    roots: Sequence[SourceRoot],
    issues: List[SourceIssue],
) -> set[Tuple[str, str]]:
    root_paths = {root.label: root.path for root in roots}
    invalid_locations = set()
    for item in files:
        path = root_paths[item.root_label] / PurePosixPath(item.relative_path)
        try:
            current = path.lstat()
        except OSError as exc:
            current = None
            message = str(exc)
        else:
            message = "Source changed after its acquisition hash was computed"
        if (
            current is None
            or stat.S_ISLNK(current.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or current.st_size != item.size_bytes
            or current.st_mtime_ns != item.modified_ns
            or current.st_dev != item.device
            or current.st_ino != item.inode
        ):
            invalid_locations.add((item.root_label, item.relative_path))
            issues.append(
                SourceIssue(
                    code="source_changed_after_hash",
                    message=message,
                    root_label=item.root_label,
                    relative_path=item.relative_path,
                    section=item.section,
                )
            )
    return invalid_locations


def _summarize_section(
    section: int,
    files: Sequence[SourceFile],
    comparisons: Sequence[PathComparison],
    authority_matches: Sequence[AuthorityMatch],
    issues: Sequence[SourceIssue],
    required_roles: Sequence[str],
) -> SectionSummary:
    section_files = [item for item in files if item.section == section]
    candidate_role_counts = Counter(
        item.candidate_role for item in section_files
    )
    authorized_role_counts = Counter(
        match.assertion.role
        for match in authority_matches
        if match.assertion.section == section and match.status == "matched"
    )
    missing_roles = [
        role
        for role in required_roles
        if not any(
            authorized_role_counts[candidate]
            for candidate in _ROLE_EQUIVALENTS.get(role, {role})
        )
    ]
    conflict_count = sum(
        comparison.status == "hash_conflict"
        for comparison in comparisons
        if comparison.section == section
    )
    issue_count = sum(
        issue.section in (None, section)
        for issue in issues
    )
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
        candidate_role_counts=dict(sorted(candidate_role_counts.items())),
        authorized_role_counts=dict(sorted(authorized_role_counts.items())),
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
    authority_assertions: Sequence[AuthorityAssertion] = (),
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
    invalid_locations = _revalidate_inventory(files, validated_roots, issues)
    authority_matches = _match_authorities(
        authority_assertions,
        files,
        validated_roots,
        requested_sections,
        invalid_locations,
        issues,
    )
    summaries = [
        _summarize_section(
            section,
            files,
            comparisons,
            authority_matches,
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
        authority_matches=authority_matches,
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
    if output.is_symlink() or (output.exists() and not output.is_file()):
        raise SourceAcquisitionError(
            "Receipt output must be a regular file path"
        )
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent,
        prefix=f".{output.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(receipt.to_dict(), handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def parse_root(value: str) -> SourceRoot:
    label, separator, path = value.partition("=")
    label = label.strip()
    path = path.strip()
    if not separator or not label or not path:
        raise argparse.ArgumentTypeError("Roots must use LABEL=/absolute/or/local/path")
    return SourceRoot(label, Path(path))


class _SourceArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise SourceAcquisitionError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = _SourceArgumentParser(
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
    parser.add_argument(
        "--authority-manifest",
        type=Path,
        help="Hash-bound authority assertions; omit for candidate inventory only",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        authority_assertions = (
            load_authority_manifest(args.authority_manifest)
            if args.authority_manifest
            else []
        )
        receipt = build_receipt(
            args.root,
            requested_sections=args.sections or PRIORITY_SECTIONS,
            required_roles=args.required_roles or DEFAULT_REQUIRED_ROLES,
            authority_assertions=authority_assertions,
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
