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

from .examiner import require_named_examiner, write_new_json
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
DRAFT_SCHEMA_ID = "dbx.page_render_crop_draft"
DRAFT_SCHEMA_VERSION = "1.0"
DRAFT_STATUS = "UNAPPROVED_DRAFT"
QUEUE_SCHEMA_ID = "dbx.crop_fill_queue"
QUEUE_SCHEMA_VERSION = "1.0"
FACE_FIELDS = ("rec_date", "grantor", "grantee")
RECEIPT_SCHEMA_ID = "dbx.page_render_export_receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
RENDER_SUFFIXES = {
    ".bmp",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
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


def _render_files(bind_dir: Path) -> List[Path]:
    try:
        children = list(bind_dir.iterdir())
    except OSError as exc:
        raise PageRenderExportError(f"Cannot read bind-dir: {exc}") from exc
    files = [
        path
        for path in children
        if path.is_file() and path.suffix.casefold() in RENDER_SUFFIXES
    ]
    return sorted(files, key=lambda path: path.name.casefold())


def empty_crop_row(page: Dict[str, object]) -> Dict[str, object]:
    """Empty face row for one hashed page. Does not invent a document number."""
    number = page.get("page")
    if type(number) is not int or number < 1:
        raise PageRenderExportError("page must be an integer >= 1")
    digest = page.get("source_sha256")
    return {
        "row_id": f"page-{number}",
        "page": number,
        "crop_id": f"page-{number}",
        "source_sha256": digest if isinstance(digest, str) else "",
        "docno": "",
        "bookpage": "",
        "rec_date": "",
        "doc_date": "",
        "grantor": "",
        "grantee": "",
    }


def _preserved_crops(
    existing: object,
    pages: Sequence[Dict[str, object]],
) -> List[Dict[str, object]]:
    """Keep examiner crop text. Seed empty rows only when crops are still empty."""
    hashes = {
        item["page"]: item.get("source_sha256")
        for item in pages
        if isinstance(item, dict) and type(item.get("page")) is int
    }
    kept: List[Dict[str, object]] = []
    if isinstance(existing, list):
        for raw in existing:
            if not isinstance(raw, dict):
                continue
            page = raw.get("page")
            if type(page) is not int:
                continue
            crop = dict(raw)
            digest = hashes.get(page)
            if isinstance(digest, str) and digest:
                crop["source_sha256"] = digest
            kept.append(crop)
    if kept:
        return kept
    return [empty_crop_row(page) for page in pages if type(page.get("page")) is int]


def write_crops_draft(
    *,
    output: Path,
    packet_id: str,
    bind_dir: Optional[Path] = None,
    paths: Optional[Sequence[Path]] = None,
) -> Dict[str, object]:
    """Hash page renders. Does not invent crop text, docnos, or page counts."""
    token = packet_id.strip()
    if not token or "\n" in token:
        raise PageRenderExportError("packet_id must be a single-line string")
    if paths and bind_dir is None:
        raise PageRenderExportError("paths requires bind-dir")
    pages: List[Dict[str, object]] = []
    bind_text = ""
    if bind_dir is not None:
        resolved = bind_dir.expanduser().resolve()
        if not resolved.is_dir():
            raise PageRenderExportError(f"bind-dir is not a directory: {resolved}")
        bind_text = str(resolved)
        files: List[Path]
        if paths:
            files = []
            for raw in paths:
                render = raw.expanduser().resolve()
                if resolved not in render.parents and render != resolved:
                    raise PageRenderExportError(
                        f"render path escapes the bind directory: {render}"
                    )
                if not render.is_file():
                    continue
                if render.suffix.casefold() not in RENDER_SUFFIXES:
                    continue
                files.append(render)
            files = sorted(
                files,
                key=lambda path: str(path.relative_to(resolved)).casefold(),
            )
        else:
            files = _render_files(resolved)
        for index, path in enumerate(files, start=1):
            pages.append(
                {
                    "page": index,
                    "path": str(path.relative_to(resolved)).replace("\\", "/"),
                    "source_sha256": sha256_file(path),
                }
            )
    dest = output.expanduser()
    existing_crops: object = []
    if dest.is_file():
        try:
            existing = json.loads(dest.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PageRenderExportError(f"Cannot read {dest}: {exc}") from exc
        if isinstance(existing, dict):
            existing_crops = existing.get("crops")
    crops = _preserved_crops(existing_crops, pages)
    draft = {
        "schema_id": DRAFT_SCHEMA_ID,
        "schema_version": DRAFT_SCHEMA_VERSION,
        "status": DRAFT_STATUS,
        "packet_id": token,
        "expected_page_count": len(pages),
        "pages": pages,
        "crops": crops,
        "bind_dir": bind_text,
        "notes": [
            "UNAPPROVED_DRAFT cannot bind page_render",
            "Fill only text visible on the hashed page render",
            "Bare document numbers stay bare; neighbouring numbers are not guessed",
        ],
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(draft, indent=2, sort_keys=True), encoding="utf-8")
    return draft


def write_crop_packet(
    *,
    draft: Dict[str, object],
    bind_dir: Path,
    output: Path,
    packet_id: Optional[str] = None,
) -> Dict[str, object]:
    """Hash page renders and keep examiner-held crop text, including blanks.

    Bare document numbers stay bare. Missing docno and bookpage together
    is refused. Neighbouring numbers are not guessed.
    """
    bind = bind_dir.expanduser().resolve()
    if not bind.is_dir():
        raise PageRenderExportError(f"bind-dir is not a directory: {bind}")
    raw_pages = draft.get("pages")
    raw_crops = draft.get("crops")
    if not isinstance(raw_pages, list) or not raw_pages:
        raise PageRenderExportError("pages must be a non-empty list")
    if not isinstance(raw_crops, list) or not raw_crops:
        raise PageRenderExportError("crops must be a non-empty list")
    expected = draft.get("expected_page_count", len(raw_pages))
    if type(expected) is not int or expected != len(raw_pages):
        raise PageRenderExportError(
            "expected_page_count must match the number of page renders"
        )
    token = _require_text(packet_id or draft.get("packet_id") or "", "packet_id")
    pages: List[Dict[str, object]] = []
    page_hashes: Dict[int, str] = {}
    for index, raw in enumerate(raw_pages):
        if not isinstance(raw, dict) or "page" not in raw or "path" not in raw:
            raise PageRenderExportError(f"pages[{index}] must have page and path")
        page = raw["page"]
        if type(page) is not int or page < 1:
            raise PageRenderExportError(f"pages[{index}] page must be an integer >= 1")
        relative = _require_text(raw["path"], "path")
        render = (bind / relative).resolve()
        if bind not in render.parents and render != bind:
            raise PageRenderExportError(f"pages[{index}] path escapes the bind directory")
        if not render.is_file():
            raise PageRenderExportError(f"pages[{index}] render is missing: {relative}")
        digest = sha256_file(render)
        page_hashes[page] = digest
        pages.append(
            {
                "page": page,
                "source_sha256": digest,
                "path": relative,
            }
        )
    crops: List[Dict[str, object]] = []
    for index, raw in enumerate(raw_crops):
        if not isinstance(raw, dict):
            raise PageRenderExportError(f"crops[{index}] must be an object")
        page = raw.get("page")
        if page not in page_hashes:
            raise PageRenderExportError(f"crops[{index}] page is not in the page list")
        crop = {
            "row_id": raw.get("row_id"),
            "page": page,
            "crop_id": raw.get("crop_id"),
            "source_sha256": page_hashes[page],
            "docno": raw.get("docno", ""),
            "bookpage": raw.get("bookpage", ""),
            "rec_date": raw.get("rec_date", ""),
            "doc_date": raw.get("doc_date", ""),
            "grantor": raw.get("grantor", ""),
            "grantee": raw.get("grantee", ""),
        }
        crops.append(crop)
    packet = {
        "schema_id": PACKET_SCHEMA_ID,
        "schema_version": PACKET_SCHEMA_VERSION,
        "packet_id": token,
        "expected_page_count": expected,
        "pages": pages,
        "crops": crops,
    }
    compile_page_renders(packet, bind_dir=bind)
    try:
        write_new_json(packet, output, "page-render crop packet")
    except ValueError as exc:
        raise PageRenderExportError(str(exc)) from exc
    return packet


def crop_fill_queue_from_draft(draft: Dict[str, object]) -> Dict[str, object]:
    """List hashed pages that still need face text. Does not invent values."""
    if not isinstance(draft, dict) or draft.get("schema_id") != DRAFT_SCHEMA_ID:
        raise PageRenderExportError("page-render crop draft schema is invalid")
    pages = draft.get("pages")
    crops = draft.get("crops")
    if not isinstance(pages, list):
        raise PageRenderExportError("pages must be a list")
    if not isinstance(crops, list):
        raise PageRenderExportError("crops must be a list")
    paths: Dict[int, object] = {}
    hashes: Dict[int, object] = {}
    for raw in pages:
        if not isinstance(raw, dict) or type(raw.get("page")) is not int:
            continue
        paths[raw["page"]] = raw.get("path") or ""
        hashes[raw["page"]] = raw.get("source_sha256") or ""
    items: List[Dict[str, object]] = []
    for raw in crops:
        if not isinstance(raw, dict) or type(raw.get("page")) is not int:
            continue
        page = raw["page"]
        docno = raw.get("docno") if isinstance(raw.get("docno"), str) else ""
        bookpage = raw.get("bookpage") if isinstance(raw.get("bookpage"), str) else ""
        missing: List[str] = []
        if not docno.strip() and not bookpage.strip():
            missing.append("docno_or_bookpage")
        for field_name in FACE_FIELDS:
            value = raw.get(field_name)
            if not isinstance(value, str) or not value.strip():
                missing.append(field_name)
        if not missing:
            continue
        items.append(
            {
                "row_id": raw.get("row_id") or f"page-{page}",
                "page": page,
                "path": paths.get(page, ""),
                "source_sha256": raw.get("source_sha256") or hashes.get(page, ""),
                "missing": missing,
                "action": "source_proved_fill",
            }
        )
    cropped_pages = {
        raw["page"]
        for raw in crops
        if isinstance(raw, dict) and type(raw.get("page")) is int
    }
    for page, digest in hashes.items():
        if page in cropped_pages:
            continue
        items.append(
            {
                "row_id": f"page-{page}",
                "page": page,
                "path": paths.get(page, ""),
                "source_sha256": digest,
                "missing": ["docno_or_bookpage", *FACE_FIELDS],
                "action": "source_proved_fill",
            }
        )
    token = draft.get("packet_id")
    return {
        "schema_id": QUEUE_SCHEMA_ID,
        "schema_version": QUEUE_SCHEMA_VERSION,
        "packet_id": token if isinstance(token, str) else "",
        "items": items,
        "notes": [
            "This queue does not invent document numbers or parties",
            "Fill only text visible on the hashed page render",
            "Bare document numbers stay bare",
        ],
    }


def write_crop_fill_queue(
    draft: Dict[str, object],
    output: Path,
) -> Dict[str, object]:
    queue = crop_fill_queue_from_draft(draft)
    dest = output.expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(queue, indent=2, sort_keys=True), encoding="utf-8")
    return queue


def attest_crops_draft(
    draft: Dict[str, object],
    *,
    bind_dir: Path,
    output: Path,
    operator: str,
    packet_id: Optional[str] = None,
) -> Dict[str, object]:
    """Promote filled crops. Horizon does not invent document numbers."""
    try:
        require_named_examiner(operator)
    except ValueError as exc:
        raise PageRenderExportError(str(exc)) from exc
    if (
        draft.get("schema_id") != DRAFT_SCHEMA_ID
        or draft.get("schema_version") != DRAFT_SCHEMA_VERSION
        or draft.get("status") != DRAFT_STATUS
    ):
        raise PageRenderExportError("page-render crop draft schema is invalid")
    return write_crop_packet(
        draft=draft,
        bind_dir=bind_dir,
        output=output,
        packet_id=packet_id,
    )


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
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--attest", action="store_true")
    parser.add_argument("--init-draft", action="store_true")
    parser.add_argument("--draft", type=Path)
    parser.add_argument("--from-draft", type=Path)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--export", type=Path)
    parser.add_argument("--bind-dir", type=Path)
    parser.add_argument("--packet-id")
    parser.add_argument("--operator")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.init_draft:
            if args.packet_id is None:
                raise PageRenderExportError("--init-draft requires --packet-id")
            draft = write_crops_draft(
                output=args.output,
                packet_id=args.packet_id,
                bind_dir=args.bind_dir,
            )
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "status": draft.get("status"),
                        "page_count": len(draft.get("pages") or []),
                        "crop_count": len(draft.get("crops") or []),
                        "packages_complete": False,
                    },
                    indent=2,
                )
            )
            return 0
        if args.attest:
            draft_path = args.from_draft or args.draft
            if draft_path is None or args.bind_dir is None or args.operator is None:
                raise PageRenderExportError(
                    "--attest requires --from-draft, --bind-dir, and "
                    "--operator; Horizon does not invent crop text"
                )
            packet = attest_crops_draft(
                _load_json(draft_path),
                bind_dir=args.bind_dir,
                output=args.output,
                operator=args.operator,
                packet_id=args.packet_id,
            )
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "page_count": len(packet["pages"]),
                        "crop_count": len(packet["crops"]),
                        "packages_complete": False,
                    },
                    indent=2,
                )
            )
            return 0
        if args.write:
            if args.draft is None or args.bind_dir is None:
                raise PageRenderExportError(
                    "--write requires --draft and --bind-dir; Horizon "
                    "does not invent crop text"
                )
            packet = write_crop_packet(
                draft=_load_json(args.draft),
                bind_dir=args.bind_dir,
                output=args.output,
                packet_id=args.packet_id,
            )
            print(
                json.dumps(
                    {
                        "output": str(args.output),
                        "page_count": len(packet["pages"]),
                        "crop_count": len(packet["crops"]),
                        "packages_complete": False,
                    },
                    indent=2,
                )
            )
            return 0
        if args.packet is None or args.export is None:
            raise PageRenderExportError("Pass --packet and --export to compile, or --write")
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
