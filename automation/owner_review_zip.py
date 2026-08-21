"""Build deterministic owner-review ZIPs from an explicit clean TURN_IN folder.

The builder intentionally does not recurse from a project/run root. This closes
an entire class of packaging defects where source PDFs and OCR corpora were
silently swept into multi-gigabyte owner-review ZIPs.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


class PackagePolicyError(ValueError):
    """Raised when a candidate package violates owner-review policy."""


_ALLOWED_AUTO_EXTENSIONS = {
    ".xlsx",
    ".xlsm",
    ".docx",
    ".txt",
    ".md",
    ".csv",
    ".json",
}
_SAFE_PDF_TOKENS = {
    "abstract",
    "certification",
    "checklist",
    "decision",
    "brief",
    "letter",
    "owner_review",
    "owner-review",
    "report",
    "runsheet",
    "summary",
    "title",
}
_PROHIBITED_DIRECTORY_TOKENS = {
    "source",
    "source_pdf",
    "source_pdfs",
    "sources",
    "raw",
    "raw_pdf",
    "raw_pdfs",
    "ocr",
    "images",
    "image",
    "text_corpus",
    "native_text",
    "reconciled_text",
    "structured_data",
    "conversion_cache",
}
_PROHIBITED_FILE_PREFIXES = ("~$", ".")
_MAX_MEMBER_BYTES = 100 * 1024 * 1024
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _normalized_parts(relative: Path) -> list[str]:
    return [part.lower().replace("-", "_").replace(" ", "_") for part in relative.parts]


def _validate_relative_path(relative: Path) -> None:
    if relative.is_absolute() or ".." in relative.parts:
        raise PackagePolicyError(f"path is outside TURN_IN: {relative}")
    if any(part in {"", "."} for part in relative.parts):
        raise PackagePolicyError(f"invalid package path: {relative}")

    directory_parts = _normalized_parts(relative.parent)
    for part in directory_parts:
        if part in _PROHIBITED_DIRECTORY_TOKENS or part.startswith("source_"):
            raise PackagePolicyError(f"prohibited source directory in package path: {relative}")

    if relative.name.startswith(_PROHIBITED_FILE_PREFIXES):
        raise PackagePolicyError(f"temporary/hidden file is not packageable: {relative}")


def _safe_join(turn_in: Path, relative_text: str) -> tuple[Path, Path]:
    relative = Path(relative_text.replace("\\", "/"))
    _validate_relative_path(relative)
    candidate = (turn_in / relative).resolve()
    try:
        candidate.relative_to(turn_in.resolve())
    except ValueError as exc:
        raise PackagePolicyError(f"path is outside TURN_IN: {relative_text}") from exc
    return candidate, relative


def _auto_pdf_allowed(relative: Path) -> bool:
    normalized = relative.stem.lower().replace(" ", "_")
    return any(token in normalized for token in _SAFE_PDF_TOKENS)


def _validate_file(path: Path, relative: Path, *, manifest_explicit: bool) -> None:
    _validate_relative_path(relative)
    if not path.is_file():
        raise PackagePolicyError(f"manifest member does not exist or is not a file: {relative}")
    if path.is_symlink():
        raise PackagePolicyError(f"symbolic links are not allowed: {relative}")

    size = path.stat().st_size
    if size > _MAX_MEMBER_BYTES:
        raise PackagePolicyError(
            f"member exceeds {_MAX_MEMBER_BYTES} byte owner-review cap: {relative} ({size} bytes)"
        )

    extension = path.suffix.lower()
    if extension == ".pdf":
        if not manifest_explicit and not _auto_pdf_allowed(relative):
            raise PackagePolicyError(
                f"unrecognized PDF may be a source document; add an explicit manifest only after review: {relative}"
            )
        return

    if extension not in _ALLOWED_AUTO_EXTENSIONS:
        raise PackagePolicyError(f"unsupported owner-review member type: {relative}")


def _load_manifest(turn_in: Path, manifest_path: Path) -> list[tuple[Path, Path]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    include = payload.get("include")
    if not isinstance(include, list) or not include:
        raise PackagePolicyError("manifest must contain a non-empty 'include' list")

    result: list[tuple[Path, Path]] = []
    seen: set[str] = set()
    for raw in include:
        if not isinstance(raw, str) or not raw.strip():
            raise PackagePolicyError("manifest include entries must be non-empty strings")
        path, relative = _safe_join(turn_in, raw)
        key = relative.as_posix().casefold()
        if key in seen:
            raise PackagePolicyError(f"duplicate manifest member: {relative}")
        seen.add(key)
        _validate_file(path, relative, manifest_explicit=True)
        result.append((path, relative))
    return sorted(result, key=lambda item: item[1].as_posix().casefold())


def _auto_collect(turn_in: Path) -> list[tuple[Path, Path]]:
    result: list[tuple[Path, Path]] = []
    errors: list[str] = []
    for path in sorted(turn_in.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_dir():
            continue
        relative = path.relative_to(turn_in)
        try:
            _validate_file(path, relative, manifest_explicit=False)
        except PackagePolicyError as exc:
            errors.append(str(exc))
            continue
        result.append((path, relative))

    if errors:
        raise PackagePolicyError("; ".join(errors))
    if not result:
        raise PackagePolicyError("TURN_IN contains no packageable deliverables")
    return result


def inspect_owner_review_zip(zip_path: str | os.PathLike[str]) -> dict[str, Any]:
    """Validate ZIP member safety, CRC/readback, duplicates, sizes, and hashes."""
    path = Path(zip_path)
    if not path.is_file():
        raise PackagePolicyError(f"ZIP does not exist: {path}")

    members: list[str] = []
    member_receipts: list[dict[str, Any]] = []
    seen: set[str] = set()
    with zipfile.ZipFile(path, "r") as archive:
        bad_crc = archive.testzip()
        if bad_crc is not None:
            raise PackagePolicyError(f"ZIP CRC/readback failed for member: {bad_crc}")

        for info in archive.infolist():
            if info.is_dir():
                continue
            posix = PurePosixPath(info.filename)
            if posix.is_absolute() or ".." in posix.parts or not posix.parts:
                raise PackagePolicyError(f"unsafe member path: {info.filename}")
            normalized = posix.as_posix().casefold()
            if normalized in seen:
                raise PackagePolicyError(f"duplicate ZIP member: {info.filename}")
            seen.add(normalized)
            data = archive.read(info)
            members.append(posix.as_posix())
            member_receipts.append(
                {
                    "path": posix.as_posix(),
                    "bytes": len(data),
                    "sha256": _sha256_bytes(data),
                }
            )

    members.sort(key=str.casefold)
    member_receipts.sort(key=lambda item: item["path"].casefold())
    return {
        "zip": str(path),
        "zip_bytes": path.stat().st_size,
        "zip_sha256": _sha256_file(path),
        "members": members,
        "member_receipts": member_receipts,
        "readback_verified": True,
    }


def build_owner_review_zip(
    turn_in_dir: str | os.PathLike[str],
    output_zip: str | os.PathLike[str],
    *,
    manifest_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Build and validate a deterministic ZIP from one clean TURN_IN directory.

    When ``manifest_path`` is omitted, all packageable files in TURN_IN are
    included and any unrecognized PDF/source-like path causes a hard failure.
    An explicit manifest can authorize a reviewed PDF name, but it cannot
    escape TURN_IN, traverse paths, include source-named directories, include
    symlinks, exceed the member size cap, or add unsupported file types.
    """
    turn_in = Path(turn_in_dir).resolve()
    output = Path(output_zip).resolve()
    if not turn_in.is_dir():
        raise PackagePolicyError(f"TURN_IN directory does not exist: {turn_in}")

    if manifest_path is not None:
        candidates = _load_manifest(turn_in, Path(manifest_path).resolve())
    else:
        candidates = _auto_collect(turn_in)

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    expected: dict[str, dict[str, Any]] = {}
    with tempfile.NamedTemporaryFile(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent, delete=False
    ) as handle:
        temp_path = Path(handle.name)

    try:
        with zipfile.ZipFile(
            temp_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            strict_timestamps=True,
        ) as archive:
            for path, relative in candidates:
                member = relative.as_posix()
                data = path.read_bytes()
                info = zipfile.ZipInfo(member, date_time=_FIXED_ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.flag_bits = 0
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
                expected[member] = {
                    "path": member,
                    "bytes": len(data),
                    "sha256": _sha256_bytes(data),
                }

        os.replace(temp_path, output)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    receipt = inspect_owner_review_zip(output)
    expected_members = sorted(expected, key=str.casefold)
    if receipt["members"] != expected_members:
        raise PackagePolicyError(
            f"ZIP member mismatch after readback: expected {expected_members}, got {receipt['members']}"
        )
    if receipt["member_receipts"] != [expected[name] for name in expected_members]:
        raise PackagePolicyError("ZIP member hash/size mismatch after readback")
    return receipt


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Build a deterministic clean owner-review ZIP from one TURN_IN folder."
    )
    parser.add_argument("--turn-in", required=True, help="Clean TURN_IN directory")
    parser.add_argument("--output", required=True, help="Output ZIP path")
    parser.add_argument("--manifest", help="Optional JSON manifest with an 'include' list")
    parser.add_argument("--receipt", help="Optional JSON receipt output path")
    args = parser.parse_args()

    try:
        receipt = build_owner_review_zip(
            args.turn_in,
            args.output,
            manifest_path=args.manifest,
        )
    except (OSError, json.JSONDecodeError, PackagePolicyError) as exc:
        parser.exit(2, f"OWNER_REVIEW_ZIP_FAILED: {exc}\n")

    if args.receipt:
        receipt_path = Path(args.receipt)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(
        f"OWNER_REVIEW_ZIP_OK output={receipt['zip']} "
        f"members={len(receipt['members'])} sha256={receipt['zip_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
