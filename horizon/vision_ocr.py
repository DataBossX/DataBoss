"""Vision-first, OCR-second face review for accounted images.

Vision is required on empty-text PDF pages and raster scans. OCR may
only target a named unreadable region. Extracted text is queued for an
examiner. It is never copied into legal, party, or date cells.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .examiner import write_new_json
from .image_account import (
    QUEUE_SCHEMA_ID,
    WORK_DATE,
    ImageAccountError,
    account_images,
    vision_queue_from_receipt,
)

RECEIPT_SCHEMA_ID = "dbx.vision_ocr_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"


class VisionOcrError(ValueError):
    """Raised when vision/OCR cannot run safely."""


@dataclass
class FaceAttempt:
    path: str
    kind: str
    source_sha256: str
    page: Optional[int]
    vision_status: str
    ocr_status: str
    tool: str
    text_bytes: int
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class VisionOcrReceipt:
    generated_utc: str
    work_date: str
    packet_id: str
    queued: int
    vision_unavailable: int
    ocr_unavailable: int
    ocr_ran: int
    attempts: List[FaceAttempt]
    technical_pass: bool
    packages_complete: bool
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(
        default_factory=lambda: [
            "Vision before OCR",
            "OCR is not a source of legal facts",
            "Do not copy extracted text into required abstract cells",
            "packages_complete stays false",
        ]
    )

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["attempts"] = [item.to_dict() for item in self.attempts]
        return payload


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\n" in value:
        raise VisionOcrError(f"{label} must be a single-line string")
    return value.strip()


def detect_tools() -> Dict[str, str]:
    return {
        "vision": "unavailable",
        "tesseract": shutil.which("tesseract") or "unavailable",
    }


def review_queue(
    queue: Dict[str, object],
    *,
    bind_dir: Optional[Path] = None,
    allow_ocr: bool = False,
) -> VisionOcrReceipt:
    if not isinstance(queue, dict) or queue.get("schema_id") != QUEUE_SCHEMA_ID:
        raise VisionOcrError("vision queue schema is invalid")
    packet_id = _require_text(queue.get("packet_id"), "packet_id")
    raw_items = queue.get("items")
    if not isinstance(raw_items, list):
        raise VisionOcrError("items must be a list")
    tools = detect_tools()
    attempts: List[FaceAttempt] = []
    vision_unavailable = 0
    ocr_unavailable = 0
    ocr_ran = 0
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            raise VisionOcrError(f"items[{index}] is invalid")
        path = _require_text(raw.get("path"), f"items[{index}] path")
        kind = _require_text(raw.get("kind"), f"items[{index}] kind")
        digest = _require_text(raw.get("source_sha256"), f"items[{index}] source_sha256")
        page = raw.get("page")
        notes = [
            "vision required before any OCR",
            "face text is review-only",
            "no authenticated vision worker is connected",
        ]
        vision_unavailable += 1
        ocr_status = "not_run"
        if allow_ocr:
            ocr_status = "blocked_until_vision"
            ocr_unavailable += 1
            notes.append("OCR blocked; vision is unavailable")
            notes.append("OCR may only target a named crop after a face is read")
        attempts.append(
            FaceAttempt(
                path=path,
                kind=kind,
                source_sha256=digest.casefold(),
                page=page if type(page) is int else None,
                vision_status="unavailable",
                ocr_status=ocr_status,
                tool="none",
                text_bytes=0,
                notes=notes,
            )
        )
    return VisionOcrReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        work_date=WORK_DATE.isoformat(),
        packet_id=packet_id,
        queued=len(attempts),
        vision_unavailable=vision_unavailable,
        ocr_unavailable=ocr_unavailable,
        ocr_ran=ocr_ran,
        attempts=attempts,
        technical_pass=True,
        packages_complete=False,
        notes=[
            "Vision before OCR",
            "OCR is not a source of legal facts",
            "Do not copy extracted text into required abstract cells",
            "packages_complete stays false",
            f"tools={tools}",
        ],
    )


def review_bind_dir(
    bind_dir: Path,
    *,
    packet_id: str,
    allow_ocr: bool = False,
) -> tuple[Dict[str, object], VisionOcrReceipt]:
    receipt = account_images(bind_dir, packet_id=packet_id)
    queue = vision_queue_from_receipt(receipt)
    return queue, review_queue(queue, bind_dir=bind_dir, allow_ocr=allow_ocr)


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VisionOcrError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise VisionOcrError(f"{path} must contain a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Queue vision-first face review for every empty-text image. "
            "OCR is optional and never writes legal cells."
        )
    )
    parser.add_argument("--bind-dir", type=Path)
    parser.add_argument("--queue", type=Path)
    parser.add_argument("--packet-id")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-ocr", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.queue is not None:
            receipt = review_queue(
                _load_json(args.queue),
                bind_dir=args.bind_dir,
                allow_ocr=args.allow_ocr,
            )
        else:
            if args.bind_dir is None or not args.packet_id:
                raise VisionOcrError("Pass --queue or --bind-dir with --packet-id")
            _queue, receipt = review_bind_dir(
                args.bind_dir,
                packet_id=args.packet_id,
                allow_ocr=args.allow_ocr,
            )
        write_new_json(receipt.to_dict(), args.output, "vision OCR receipt")
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "work_date": WORK_DATE.isoformat(),
                    "queued": receipt.queued,
                    "vision_unavailable": receipt.vision_unavailable,
                    "ocr_ran": receipt.ocr_ran,
                    "packages_complete": False,
                },
                indent=2,
            )
        )
    except (OSError, VisionOcrError, ImageAccountError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
