"""Count every image in a bind directory and account for each one.

A raster file is one image. Each PDF page is one image. The PDF file
itself is a container, not a second image. Other files are listed so
they cannot hide in the folder. This is not OCR, not vision review,
and not package release. UNKNOWN stays UNKNOWN.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .examiner import write_new_json
from .isolated_delta import sha256_file
from .pdf_census import EMPTY_TEXT_LIMIT, count_pdf_pages

WORK_DATE = date(2026, 9, 22)
WORK_DATE_TOKEN = "20260922"
PACKET_SCHEMA_ID = "dbx.image_account_packet"
PACKET_SCHEMA_VERSION = "1.0"
RECEIPT_SCHEMA_ID = "dbx.image_account_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
QUEUE_SCHEMA_ID = "dbx.image_account_queue"
QUEUE_SCHEMA_VERSION = "1.0"
RASTER_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".gif", ".webp", ".bmp"}
)
SKIP_DIR_NAMES = frozenset({".git", "node_modules", "__pycache__", "output"})


class ImageAccountError(ValueError):
    """Raised when an image census cannot be bound safely."""


@dataclass
class ImageRecord:
    path: str
    kind: str
    source_sha256: str
    size_bytes: int
    page: Optional[int]
    accounted: bool
    empty_text: bool
    vision_status: str
    ocr_status: str
    disposition: str
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class ImageAccountReceipt:
    generated_utc: str
    work_date: str
    packet_id: str
    bind_dir: str
    file_count: int
    image_count: int
    raster_count: int
    pdf_page_count: int
    other_file_count: int
    accounted_images: int
    unaccounted_images: int
    empty_text_images: int
    images: List[ImageRecord]
    technical_pass: bool
    packages_complete: bool
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(
        default_factory=lambda: [
            "Every raster file and every PDF page must appear once",
            "PDF containers are listed separately and are not extra images",
            "empty_text images stay held until a face is read",
            "This is not OCR, not vision review, and not package release",
            "packages_complete stays false",
        ]
    )

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["images"] = [item.to_dict() for item in self.images]
        return payload


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value:
        raise ImageAccountError(f"{label} must be a single-line string")
    return value.strip()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def iter_bind_files(bind_dir: Path) -> List[Path]:
    bind = bind_dir.expanduser().resolve()
    if not bind.is_dir():
        raise ImageAccountError(f"bind-dir is not a directory: {bind}")
    found: List[Path] = []
    for path in sorted(bind.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(bind)
        if any(part.startswith(".") or part in SKIP_DIR_NAMES for part in relative.parts):
            continue
        found.append(path)
    return found


def _relative(path: Path, bind: Path) -> str:
    return path.relative_to(bind).as_posix()


def _raster_record(path: Path, bind: Path) -> ImageRecord:
    digest = sha256_file(path)
    return ImageRecord(
        path=_relative(path, bind),
        kind="raster",
        source_sha256=digest,
        size_bytes=path.stat().st_size,
        page=1,
        accounted=True,
        empty_text=True,
        vision_status="queued",
        ocr_status="not_run",
        disposition="vision_queue",
        issues=["raster has no text layer; vision before OCR"],
    )


def _other_record(path: Path, bind: Path) -> ImageRecord:
    return ImageRecord(
        path=_relative(path, bind),
        kind="other",
        source_sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
        page=None,
        accounted=True,
        empty_text=False,
        vision_status="not_applicable",
        ocr_status="not_applicable",
        disposition="not_an_image",
    )


def _pdf_records(path: Path, bind: Path) -> List[ImageRecord]:
    relative = _relative(path, bind)
    data = path.read_bytes()
    digest = sha256_file(path)
    issues: List[str] = []
    if not data.startswith(b"%PDF"):
        issues.append("file is not a PDF")
        return [
            ImageRecord(
                path=relative,
                kind="pdf_container",
                source_sha256=digest,
                size_bytes=len(data),
                page=None,
                accounted=False,
                empty_text=True,
                vision_status="queued",
                ocr_status="not_run",
                disposition="unaccounted",
                issues=issues,
            )
        ]
    counted, declared, text_bytes = count_pdf_pages(data)
    empty_text = text_bytes < EMPTY_TEXT_LIMIT
    if counted < 1:
        issues.append("counted 0 pages")
    if declared is not None and declared != counted:
        issues.append(
            f"page-tree Count {declared} disagrees with counted {counted}"
        )
    container = ImageRecord(
        path=relative,
        kind="pdf_container",
        source_sha256=digest,
        size_bytes=len(data),
        page=None,
        accounted=counted >= 1 and not issues,
        empty_text=empty_text,
        vision_status="not_applicable",
        ocr_status="not_applicable",
        disposition="container" if counted >= 1 and not issues else "unaccounted",
        issues=list(issues),
    )
    pages: List[ImageRecord] = []
    for page in range(1, max(counted, 0) + 1):
        page_issues = list(issues)
        if empty_text:
            page_issues.append("extracted text is empty or nearly empty")
        pages.append(
            ImageRecord(
                path=f"{relative}#page={page}",
                kind="pdf_page",
                source_sha256=digest,
                size_bytes=len(data),
                page=page,
                accounted=counted >= 1 and not issues,
                empty_text=empty_text,
                vision_status="queued" if empty_text else "not_required",
                ocr_status="not_run",
                disposition="empty_text_hold" if empty_text else "accounted",
                issues=page_issues,
            )
        )
    return [container, *pages]


def inventory_bind_dir(bind_dir: Path) -> List[ImageRecord]:
    bind = bind_dir.expanduser().resolve()
    records: List[ImageRecord] = []
    for path in iter_bind_files(bind):
        suffix = path.suffix.casefold()
        if suffix in RASTER_SUFFIXES:
            records.append(_raster_record(path, bind))
        elif suffix == ".pdf":
            records.extend(_pdf_records(path, bind))
        else:
            records.append(_other_record(path, bind))
    return records


def account_images(
    bind_dir: Path,
    *,
    packet_id: str,
) -> ImageAccountReceipt:
    token = _require_text(packet_id, "packet_id")
    bind = bind_dir.expanduser().resolve()
    records = inventory_bind_dir(bind)
    images = [item for item in records if item.kind in {"raster", "pdf_page"}]
    containers = [item for item in records if item.kind == "pdf_container"]
    others = [item for item in records if item.kind == "other"]
    unaccounted = [
        item
        for item in images
        if not item.accounted or item.disposition == "unaccounted"
    ]
    empty_text = [item for item in images if item.empty_text]
    technical_pass = bool(images) and not unaccounted and all(
        not item.issues or item.issues == ["extracted text is empty or nearly empty"]
        or item.issues == ["raster has no text layer; vision before OCR"]
        for item in images
    )
    if any(item.disposition == "unaccounted" for item in containers):
        technical_pass = False
    return ImageAccountReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        work_date=WORK_DATE.isoformat(),
        packet_id=token,
        bind_dir=str(bind),
        file_count=len(iter_bind_files(bind)),
        image_count=len(images),
        raster_count=sum(1 for item in images if item.kind == "raster"),
        pdf_page_count=sum(1 for item in images if item.kind == "pdf_page"),
        other_file_count=len(others),
        accounted_images=len(images) - len(unaccounted),
        unaccounted_images=len(unaccounted),
        empty_text_images=len(empty_text),
        images=records,
        technical_pass=technical_pass,
        packages_complete=False,
    )


def every_image_accounted(receipt: ImageAccountReceipt) -> bool:
    images = [item for item in receipt.images if item.kind in {"raster", "pdf_page"}]
    if not images:
        return False
    paths = [item.path for item in images]
    return (
        receipt.unaccounted_images == 0
        and receipt.accounted_images == receipt.image_count
        and len(paths) == len(set(paths))
        and all(item.accounted for item in images)
    )


def vision_queue_from_receipt(receipt: ImageAccountReceipt) -> Dict[str, object]:
    items = []
    for item in receipt.images:
        if item.kind not in {"raster", "pdf_page"}:
            continue
        if item.vision_status not in {"queued"} and not item.empty_text:
            continue
        items.append(
            {
                "path": item.path,
                "kind": item.kind,
                "source_sha256": item.source_sha256,
                "page": item.page,
                "action": "face_review",
                "vision_first": True,
                "ocr_allowed": "region_only",
            }
        )
    return {
        "schema_id": QUEUE_SCHEMA_ID,
        "schema_version": QUEUE_SCHEMA_VERSION,
        "packet_id": receipt.packet_id,
        "work_date": WORK_DATE.isoformat(),
        "items": items,
        "notes": [
            "Vision before OCR",
            "OCR may only target a specific unreadable region",
            "This queue does not invent legal, party, or date values",
        ],
    }


def write_inventory_packet(
    *,
    bind_dir: Path,
    output: Path,
    packet_id: str,
) -> Dict[str, object]:
    receipt = account_images(bind_dir, packet_id=packet_id)
    packet = {
        "schema_id": PACKET_SCHEMA_ID,
        "schema_version": PACKET_SCHEMA_VERSION,
        "packet_id": receipt.packet_id,
        "work_date": WORK_DATE.isoformat(),
        "bind_dir": receipt.bind_dir,
        "image_count": receipt.image_count,
        "files": [
            {
                "path": item.path,
                "kind": item.kind,
                "source_sha256": item.source_sha256,
                "page": item.page,
            }
            for item in receipt.images
            if item.kind in {"raster", "pdf_page", "pdf_container"}
        ],
    }
    write_new_json(packet, output, "image account packet")
    return packet


def verify_packet(packet: Dict[str, object], bind_dir: Path) -> ImageAccountReceipt:
    if not isinstance(packet, dict):
        raise ImageAccountError("image account packet must be an object")
    if (
        packet.get("schema_id") != PACKET_SCHEMA_ID
        or packet.get("schema_version") != PACKET_SCHEMA_VERSION
    ):
        raise ImageAccountError("image account packet schema is invalid")
    token = _require_text(packet.get("packet_id"), "packet_id")
    live = account_images(bind_dir, packet_id=token)
    listed = packet.get("files")
    if not isinstance(listed, list) or not listed:
        raise ImageAccountError("files must be a non-empty list")
    expected = {
        (item.path, item.kind, item.page)
        for item in live.images
        if item.kind in {"raster", "pdf_page"}
    }
    seen = set()
    for index, raw in enumerate(listed):
        if not isinstance(raw, dict):
            raise ImageAccountError(f"files[{index}] is invalid")
        kind = raw.get("kind")
        if kind not in {"raster", "pdf_page"}:
            continue
        path = _require_text(raw.get("path"), f"files[{index}] path")
        page = raw.get("page")
        if kind == "pdf_page" and (type(page) is not int or page < 1):
            raise ImageAccountError(f"files[{index}] page must be an integer >= 1")
        digest = raw.get("source_sha256")
        if isinstance(digest, str):
            digest = digest.casefold()
        if not _is_sha256(digest):
            raise ImageAccountError(f"files[{index}] source_sha256 is invalid")
        key = (path, kind, page if kind == "pdf_page" else 1)
        seen.add(key)
        match = next(
            (
                item
                for item in live.images
                if item.path == path and item.kind == kind
            ),
            None,
        )
        if match is None or match.source_sha256 != digest:
            live.technical_pass = False
            live.unaccounted_images += 1
            live.notes.append(f"packet image {path} does not match bind-dir bytes")
    missing = expected - seen
    extra = seen - expected
    if missing or extra:
        live.technical_pass = False
        live.unaccounted_images = max(live.unaccounted_images, len(missing) + len(extra))
        if missing:
            live.notes.append(f"{len(missing)} bind-dir image(s) are missing from the packet")
        if extra:
            live.notes.append(f"{len(extra)} packet image(s) are not in bind-dir")
    return live


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ImageAccountError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ImageAccountError(f"{path} must contain a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Count every raster and PDF page in bind-dir and account for "
            "each image. Dated 2026-09-22. Not package release."
        )
    )
    parser.add_argument("--bind-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--packet-id", required=True)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument("--vision-queue", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.inventory:
            if args.packet is not None:
                raise ImageAccountError("--inventory cannot be combined with --packet")
            packet = write_inventory_packet(
                bind_dir=args.bind_dir,
                output=args.output,
                packet_id=args.packet_id,
            )
            receipt = account_images(args.bind_dir, packet_id=args.packet_id)
        else:
            if args.packet is None:
                receipt = account_images(args.bind_dir, packet_id=args.packet_id)
            else:
                receipt = verify_packet(_load_json(args.packet), args.bind_dir)
            dest = args.output.expanduser()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(
                json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            packet = None
        if args.vision_queue is not None:
            write_new_json(
                vision_queue_from_receipt(receipt),
                args.vision_queue,
                "image account vision queue",
            )
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "work_date": WORK_DATE.isoformat(),
                    "image_count": receipt.image_count,
                    "accounted_images": receipt.accounted_images,
                    "unaccounted_images": receipt.unaccounted_images,
                    "empty_text_images": receipt.empty_text_images,
                    "every_image_accounted": every_image_accounted(receipt),
                    "technical_pass": receipt.technical_pass,
                    "packages_complete": False,
                    "packet_written": packet is not None,
                },
                indent=2,
            )
        )
    except (OSError, ImageAccountError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0 if receipt.technical_pass and every_image_accounted(receipt) else 2


if __name__ == "__main__":
    raise SystemExit(main())
