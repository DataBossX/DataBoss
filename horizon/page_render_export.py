"""Compile writer-held page-render crops into a tract-ledger export.

The compiler does not open Drive, run OCR, guess a neighbouring document
number, or drop bare-docno rows. It only binds crops to page hashes and
emits the export the re-extraction gate already consumes.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .isolated_delta import sha256_file
from .reextraction_gate import (
    EXPORT_SCHEMA_ID,
    EXPORT_SCHEMA_VERSION,
    REQUIRED_ROW_KEYS,
    assess_ledger,
    parse_ledger_export,
)
from .stable_key import StableKeyError, normalize_bookpage, normalize_docno

PACKET_SCHEMA_ID = "dbx.page_render_crop_packet"
PACKET_SCHEMA_VERSION = "1.0"
RECEIPT_SCHEMA_ID = "dbx.page_render_export_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
REQUIRED_PACKET_KEYS = {
    "schema_id",
    "schema_version",
    "packet_id",
    "expected_page_count",
    "pages",
    "crops",
}
REQUIRED_PAGE_KEYS = {"page", "source_sha256"}
REQUIRED_CROP_KEYS = {
    "row_id",
    "page",
    "crop_id",
    "source_sha256",
    "docno",
    "bookpage",
    "rec_date",
    "doc_date",
    "grantor",
    "grantee",
}


class PageRenderExportError(ValueError):
    """Raised when a page-render crop packet is unsafe."""


@dataclass
class PageRenderExportReceipt:
    generated_utc: str
    packet_id: str
    page_count: int
    crop_count: int
    tract_export: Dict[str, object]
    reextraction_technical_pass: bool
    next_action: str
    technical_pass: bool
    schema_id: str = RECEIPT_SCHEMA_ID
    schema_version: str = RECEIPT_SCHEMA_VERSION
    notes: List[str] = field(
        default_factory=lambda: [
            "Bare document-number crops are preserved; they are not guessed",
            "technical_pass is not package release",
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


def _require_text(value: object, label: str, *, allow_blank: bool = False) -> str:
    if not isinstance(value, str) or "\n" in value:
        raise PageRenderExportError(f"{label} must be a single-line string")
    if ",," in value:
        raise PageRenderExportError(f"{label} value is unsafe")
    text = value.strip()
    if not allow_blank and not text:
        raise PageRenderExportError(f"{label} must be a non-empty string")
    return text


def _require_sha256(value: object, label: str) -> str:
    digest = value.casefold() if isinstance(value, str) else ""
    if not _is_sha256(digest):
        raise PageRenderExportError(f"{label} has an invalid source_sha256")
    return digest


def compile_page_renders(
    payload: Dict[str, object],
    *,
    bind_dir: Optional[Path] = None,
) -> PageRenderExportReceipt:
    if set(payload) != REQUIRED_PACKET_KEYS:
        raise PageRenderExportError(
            "Page-render crop packet has invalid top-level fields"
        )
    if (
        payload["schema_id"] != PACKET_SCHEMA_ID
        or payload["schema_version"] != PACKET_SCHEMA_VERSION
    ):
        raise PageRenderExportError("Page-render crop packet schema is invalid")
    packet_id = _require_text(payload["packet_id"], "packet_id")
    expected = payload["expected_page_count"]
    if type(expected) is not int or expected < 1:
        raise PageRenderExportError(
            "expected_page_count must be an integer >= 1"
        )
    raw_pages = payload["pages"]
    raw_crops = payload["crops"]
    if not isinstance(raw_pages, list) or not raw_pages:
        raise PageRenderExportError("pages must be a non-empty list")
    if not isinstance(raw_crops, list) or not raw_crops:
        raise PageRenderExportError("crops must be a non-empty list")
    if len(raw_pages) != expected:
        raise PageRenderExportError(
            f"expected_page_count {expected} does not match pages {len(raw_pages)}"
        )
    pages: Dict[int, str] = {}
    for index, raw in enumerate(raw_pages):
        if not isinstance(raw, dict):
            raise PageRenderExportError(f"pages[{index}] has invalid fields")
        extra = set(raw) - REQUIRED_PAGE_KEYS - {"path"}
        missing = REQUIRED_PAGE_KEYS - set(raw)
        if extra or missing:
            raise PageRenderExportError(f"pages[{index}] has invalid fields")
        page = raw["page"]
        if type(page) is not int or page < 1:
            raise PageRenderExportError(
                f"pages[{index}] page must be an integer >= 1"
            )
        if page in pages:
            raise PageRenderExportError(f"page {page} is duplicated")
        digest = _require_sha256(raw["source_sha256"], f"pages[{index}]")
        if "path" in raw:
            if bind_dir is None:
                raise PageRenderExportError(
                    "pages[].path requires --bind-dir to rehash the render"
                )
            render = (bind_dir / _require_text(raw["path"], "path")).resolve()
            if bind_dir.resolve() not in render.parents and render != bind_dir.resolve():
                raise PageRenderExportError(
                    f"pages[{index}] path escapes the bind directory"
                )
            actual = sha256_file(render)
            if actual != digest:
                raise PageRenderExportError(
                    f"pages[{index}] hash does not match the render file"
                )
        pages[page] = digest

    rows: List[Dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_crops):
        if not isinstance(raw, dict) or set(raw) != REQUIRED_CROP_KEYS:
            raise PageRenderExportError(f"crops[{index}] has invalid fields")
        row_id = _require_text(raw["row_id"], "row_id")
        if row_id in seen_ids:
            raise PageRenderExportError(f"row_id is duplicated: {row_id}")
        seen_ids.add(row_id)
        page = raw["page"]
        if type(page) is not int or page < 1:
            raise PageRenderExportError(f"{row_id} page must be an integer >= 1")
        if page not in pages:
            raise PageRenderExportError(
                f"{row_id} page {page} is not in the page-render list"
            )
        digest = _require_sha256(raw["source_sha256"], row_id)
        if digest != pages[page]:
            raise PageRenderExportError(
                f"{row_id} source_sha256 does not match page {page}"
            )
        docno = _require_text(raw["docno"], "docno", allow_blank=True)
        bookpage = _require_text(raw["bookpage"], "bookpage", allow_blank=True)
        if not docno and not bookpage:
            raise PageRenderExportError(
                f"{row_id} has neither docno nor bookpage; refusing to invent one"
            )
        try:
            normalize_docno(docno or None)
            normalize_bookpage(bookpage or None)
        except StableKeyError as exc:
            raise PageRenderExportError(f"{row_id}: {exc}") from exc
        rows.append(
            {
                "row_id": row_id,
                "docno": docno,
                "bookpage": bookpage,
                "rec_date": _require_text(
                    raw["rec_date"], "rec_date", allow_blank=True
                ),
                "doc_date": _require_text(
                    raw["doc_date"], "doc_date", allow_blank=True
                ),
                "grantor": _require_text(
                    raw["grantor"], "grantor", allow_blank=True
                ),
                "grantee": _require_text(
                    raw["grantee"], "grantee", allow_blank=True
                ),
                "page": page,
                "crop_id": _require_text(raw["crop_id"], "crop_id"),
            }
        )
        if set(rows[-1]) != REQUIRED_ROW_KEYS:
            raise PageRenderExportError(f"{row_id} export row drifted")

    tract_export = {
        "schema_id": EXPORT_SCHEMA_ID,
        "schema_version": EXPORT_SCHEMA_VERSION,
        "packet_id": packet_id,
        "rows": rows,
    }
    export_id, ledger_rows = parse_ledger_export(tract_export)
    recon = assess_ledger(export_id, ledger_rows)
    return PageRenderExportReceipt(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        packet_id=packet_id,
        page_count=len(pages),
        crop_count=len(rows),
        tract_export=tract_export,
        reextraction_technical_pass=recon.technical_pass,
        next_action=recon.next_action,
        technical_pass=True,
    )


def _load_json(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PageRenderExportError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PageRenderExportError(f"{path} must contain a JSON object")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compile page-render crops into a tract-ledger export. "
            "Does not guess document numbers."
        )
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--bind-dir", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        receipt = compile_page_renders(
            _load_json(args.packet),
            bind_dir=args.bind_dir,
        )
        args.export.write_text(
            json.dumps(receipt.tract_export, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        args.output.write_text(
            json.dumps(receipt.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except (OSError, PageRenderExportError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "export": str(args.export),
                "crop_count": receipt.crop_count,
                "reextraction_technical_pass": receipt.reextraction_technical_pass,
                "next_action": receipt.next_action,
            },
            indent=2,
        )
    )
    return 0 if receipt.reextraction_technical_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
