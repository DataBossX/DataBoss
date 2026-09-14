"""Hash-bound PDF page census without guessing a page count.

Counts ``/Type /Page`` objects and compares them to the page-tree ``/Count``.
Extracted text bytes are a lower bound from decompressed streams, used to
flag image-only parts. This is not OCR and not package release.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .examiner import write_new_json
from .isolated_delta import sha256_file

PACKET_SCHEMA_ID = "dbx.pdf_page_census_packet"
PACKET_SCHEMA_VERSION = "1.0"
RECEIPT_SCHEMA_ID = "dbx.pdf_page_census_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
QUEUE_SCHEMA_ID = "dbx.empty_text_pdf_queue"
QUEUE_SCHEMA_VERSION = "1.0"
REQUIRED_PACKET_KEYS = {
    "schema_id",
    "schema_version",
    "packet_id",
    "files",
}
REQUIRED_FILE_KEYS = {"path", "source_sha256", "expected_pages"}
EMPTY_TEXT_LIMIT = 32


class PdfCensusError(ValueError):
    """Raised when a PDF census packet or file is unsafe."""


@dataclass
class PdfFileCensus:
    path: str
    source_sha256: str
    counted_pages: int
    declared_pages: Optional[int]
    expected_pages: int
    page_count_agrees: bool
    extracted_text_bytes: int
    empty_text: bool
    issues: List[str]


@dataclass
class PdfCensusReceipt:
    generated_utc: str
    packet_id: str
    files: List[PdfFileCensus]
    empty_text_files: int
    technical_pass: bool
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(
        default_factory=lambda: [
            "empty_text means decompressed streams had almost no extractable text",
            "This is not OCR and not package release",
        ]
    )

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value:
        raise PdfCensusError(f"{label} must be a single-line string")
    return value.strip()


def count_pdf_pages(data: bytes) -> tuple[int, Optional[int], int]:
    blobs = [data]
    text_bytes = 0
    for match in re.finditer(rb"stream\r?\n", data):
        start = match.end()
        end = data.find(b"endstream", start)
        if end == -1:
            continue
        payload = data[start:end]
        try:
            payload = zlib.decompress(payload)
        except zlib.error:
            pass
        blobs.append(payload)
        text_bytes += sum(1 for byte in payload if 32 <= byte < 127)
    joined = b"\n".join(blobs)
    pages = len(re.findall(rb"/Type\s*/Page(?![sA-Za-z])", joined))
    counts = [
        int(item)
        for item in re.findall(rb"/Type\s*/Pages[^>]*?/Count\s+(\d+)", joined)
    ]
    declared = max(counts) if counts else None
    return pages, declared, text_bytes


def iter_bind_pdfs(bind_dir: Path) -> List[Path]:
    bind = bind_dir.expanduser().resolve()
    if not bind.is_dir():
        raise PdfCensusError(f"bind-dir is not a directory: {bind}")
    found: List[Path] = []
    for path in sorted(bind.rglob("*")):
        if not path.is_file() or path.suffix.casefold() != ".pdf":
            continue
        relative = path.relative_to(bind)
        if any(part.startswith(".") for part in relative.parts):
            continue
        found.append(path)
    return found


def _measure_pdf(path: Path, bind: Path) -> Dict[str, object]:
    relative = path.relative_to(bind).as_posix()
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise PdfCensusError(f"{relative} is not a PDF")
    counted, declared, _text_bytes = count_pdf_pages(data)
    if counted < 1:
        raise PdfCensusError(f"{relative} counted 0 pages")
    if declared is not None and declared != counted:
        raise PdfCensusError(
            f"{relative} page-tree Count {declared} disagrees with "
            f"counted {counted}"
        )
    return {
        "path": relative,
        "source_sha256": sha256_file(path),
        "expected_pages": counted,
    }


def write_inventory_packet(
    *,
    bind_dir: Path,
    output: Path,
    packet_id: str,
    paths: Optional[Sequence[Path]] = None,
) -> Dict[str, object]:
    """Measure PDFs in bind-dir. expected_pages is the counted page total.

    This does not invent legal text and does not copy a federal row count
    into expected_pages. Page-tree Count must agree with /Type /Page.
    Pass ``paths`` to measure an authorized subset instead of every PDF.
    """
    token = _require_text(packet_id, "packet_id")
    bind = bind_dir.expanduser().resolve()
    if paths is None:
        selected = iter_bind_pdfs(bind)
    else:
        selected = []
        for path in paths:
            resolved = path.expanduser().resolve()
            if bind not in resolved.parents and resolved != bind:
                raise PdfCensusError(f"{resolved} escapes the bind directory")
            if not resolved.is_file() or resolved.suffix.casefold() != ".pdf":
                raise PdfCensusError(f"{resolved} is not a PDF file")
            selected.append(resolved)
        selected = sorted(set(selected))
    files: List[Dict[str, object]] = []
    for path in selected:
        files.append(_measure_pdf(path, bind))
    if not files:
        raise PdfCensusError("bind-dir contains no PDF files")
    packet: Dict[str, object] = {
        "schema_id": PACKET_SCHEMA_ID,
        "schema_version": PACKET_SCHEMA_VERSION,
        "packet_id": token,
        "files": files,
    }
    census_packet(packet, bind_dir=bind)
    try:
        write_new_json(packet, output, "PDF page census packet")
    except ValueError as exc:
        raise PdfCensusError(str(exc)) from exc
    return packet


def census_file(path: Path, expected_pages: int, expected_sha: str) -> PdfFileCensus:
    path = path.expanduser().resolve()
    digest = sha256_file(path)
    issues: List[str] = []
    if digest != expected_sha:
        issues.append("hash mismatch")
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        issues.append("file is not a PDF")
        return PdfFileCensus(
            path=str(path),
            source_sha256=digest,
            counted_pages=0,
            declared_pages=None,
            expected_pages=expected_pages,
            page_count_agrees=False,
            extracted_text_bytes=0,
            empty_text=True,
            issues=issues,
        )
    counted, declared, text_bytes = count_pdf_pages(data)
    empty_text = text_bytes < EMPTY_TEXT_LIMIT
    agrees = counted == expected_pages and (
        declared is None or declared == counted
    )
    if counted != expected_pages:
        issues.append(
            f"counted {counted} pages, expected {expected_pages}"
        )
    if declared is not None and declared != counted:
        issues.append(
            f"page-tree Count {declared} disagrees with counted {counted}"
        )
    if empty_text:
        issues.append("extracted text is empty or nearly empty")
    return PdfFileCensus(
        path=str(path),
        source_sha256=digest,
        counted_pages=counted,
        declared_pages=declared,
        expected_pages=expected_pages,
        page_count_agrees=agrees,
        extracted_text_bytes=text_bytes,
        empty_text=empty_text,
        issues=issues,
    )


def census_packet(
    payload: Dict[str, object],
    *,
    bind_dir: Path,
) -> PdfCensusReceipt:
    if set(payload) != REQUIRED_PACKET_KEYS:
        raise PdfCensusError("PDF census packet has invalid top-level fields")
    if (
        payload["schema_id"] != PACKET_SCHEMA_ID
        or payload["schema_version"] != PACKET_SCHEMA_VERSION
    ):
        raise PdfCensusError("PDF census packet schema is invalid")
    packet_id = _require_text(payload["packet_id"], "packet_id")
    raw_files = payload["files"]
    if not isinstance(raw_files, list) or not raw_files:
        raise PdfCensusError("files must be a non-empty list")
    bind_dir = bind_dir.expanduser().resolve()
    files: List[PdfFileCensus] = []
    for index, raw in enumerate(raw_files):
        if not isinstance(raw, dict) or set(raw) != REQUIRED_FILE_KEYS:
            raise PdfCensusError(f"files[{index}] has invalid fields")
        relative = Path(_require_text(raw["path"], "path"))
        if relative.is_absolute() or ".." in relative.parts:
            raise PdfCensusError(f"files[{index}] path must be a relative file")
        target = (bind_dir / relative).resolve()
        if bind_dir not in target.parents and target != bind_dir:
            raise PdfCensusError(f"files[{index}] path escapes the bind directory")
        digest = raw["source_sha256"]
        if isinstance(digest, str):
            digest = digest.casefold()
        if not _is_sha256(digest):
            raise PdfCensusError(f"files[{index}] source_sha256 is invalid")
        expected = raw["expected_pages"]
        if type(expected) is not int or expected < 1:
            raise PdfCensusError(
                f"files[{index}] expected_pages must be an integer >= 1"
            )
        files.append(census_file(target, expected, digest))
    empty_text_files = sum(1 for item in files if item.empty_text)
    # Hash/count mismatches fail. Empty text is a hold, not a compile error:
    # Part 4 image-only PDFs are expected to be empty-text and must stay visible.
    technical_pass = all(
        not any(issue != "extracted text is empty or nearly empty" for issue in item.issues)
        for item in files
    )
    return PdfCensusReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        packet_id=packet_id,
        files=files,
        empty_text_files=empty_text_files,
        technical_pass=technical_pass,
    )


def empty_text_queue_from_census(
    packet: Dict[str, object],
    receipt: PdfCensusReceipt,
) -> Dict[str, object]:
    """List image-only PDFs. Does not invent legal, party, or date values."""
    if not isinstance(packet, dict) or packet.get("schema_id") != PACKET_SCHEMA_ID:
        raise PdfCensusError("PDF census packet schema is invalid")
    raw_files = packet.get("files")
    if not isinstance(raw_files, list) or len(raw_files) != len(receipt.files):
        raise PdfCensusError("census receipt does not match the packet files")
    items: List[Dict[str, object]] = []
    for raw, measured in zip(raw_files, receipt.files):
        if not measured.empty_text:
            continue
        path = raw.get("path") if isinstance(raw, dict) else None
        items.append(
            {
                "path": path if isinstance(path, str) else measured.path,
                "source_sha256": measured.source_sha256,
                "counted_pages": measured.counted_pages,
                "extracted_text_bytes": measured.extracted_text_bytes,
                "action": "face_review",
            }
        )
    return {
        "schema_id": QUEUE_SCHEMA_ID,
        "schema_version": QUEUE_SCHEMA_VERSION,
        "packet_id": receipt.packet_id,
        "items": items,
        "notes": [
            "This queue does not invent legal, party, or date values",
            "Image-only PDFs stay empty-text until a face is read",
            "Do not copy a page count into a legal description",
        ],
    }


def write_empty_text_queue(
    packet: Dict[str, object],
    receipt: PdfCensusReceipt,
    output: Path,
) -> Dict[str, object]:
    queue = empty_text_queue_from_census(packet, receipt)
    dest = output.expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(queue, indent=2, sort_keys=True), encoding="utf-8")
    return queue


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PdfCensusError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PdfCensusError(f"{path} must contain a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Hash-bound PDF page census. Inventory measures counted pages; "
            "it does not guess a federal row count."
        )
    )
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--bind-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--inventory",
        action="store_true",
        help=(
            "Walk bind-dir, hash each PDF, and write a census packet whose "
            "expected_pages equals the counted /Type /Page total"
        ),
    )
    parser.add_argument("--packet-id")
    parser.add_argument("--empty-text-queue", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.inventory:
            if args.packet is not None:
                raise PdfCensusError("--inventory cannot be combined with --packet")
            if not args.packet_id:
                raise PdfCensusError("--inventory requires --packet-id")
            packet = write_inventory_packet(
                bind_dir=args.bind_dir,
                output=args.output,
                packet_id=args.packet_id,
            )
            receipt = census_packet(packet, bind_dir=args.bind_dir)
            if args.empty_text_queue is not None:
                write_empty_text_queue(packet, receipt, args.empty_text_queue)
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "packet_id": packet["packet_id"],
                        "file_count": len(packet["files"]),
                        "empty_text_files": receipt.empty_text_files,
                        "files": [
                            {
                                "path": item["path"],
                                "expected_pages": item["expected_pages"],
                            }
                            for item in packet["files"]
                        ],
                        "packages_complete": False,
                    },
                    indent=2,
                )
            )
            return 0
        if args.packet is None:
            raise PdfCensusError(
                "Pass --packet to verify a census packet, or --inventory "
                "to measure bind-dir"
            )
        packet = _load_json(args.packet)
        receipt = census_packet(packet, bind_dir=args.bind_dir)
        if args.empty_text_queue is not None:
            write_empty_text_queue(packet, receipt, args.empty_text_queue)
        args.output.write_text(
            json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except (OSError, PdfCensusError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "technical_pass": receipt.technical_pass,
                "empty_text_files": receipt.empty_text_files,
            },
            indent=2,
        )
    )
    return 0 if receipt.technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
