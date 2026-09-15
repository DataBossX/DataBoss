"""Hash handwritten-index scans without inventing Penterra rows.

Filename classification is not legal authority. Phase 1 live scans stay
out unless the examiner copies them into sectionN-handwritten-scans/.
This is not OCR and not package release.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .isolated_delta import sha256_file
from .source_acquisition import IMAGE_EXTENSIONS

DRAFT_SCHEMA_ID = "dbx.handwritten_scan_draft"
DRAFT_SCHEMA_VERSION = "1.0"
DRAFT_STATUS = "UNAPPROVED_DRAFT"
QUEUE_SCHEMA_ID = "dbx.handwritten_scan_queue"
QUEUE_SCHEMA_VERSION = "1.0"
SCAN_SUFFIXES = {".pdf", *IMAGE_EXTENSIONS}


class HandwrittenScanError(ValueError):
    """Raised when a handwritten-scan draft cannot be written safely."""


def _scan_files(bind_dir: Path) -> List[Path]:
    try:
        children = list(bind_dir.iterdir())
    except OSError as exc:
        raise HandwrittenScanError(f"Cannot read bind-dir: {exc}") from exc
    files = [
        path
        for path in children
        if path.is_file() and path.suffix.casefold() in SCAN_SUFFIXES
    ]
    return sorted(files, key=lambda path: path.name.casefold())


def write_handwritten_scan_draft(
    *,
    output: Path,
    packet_id: str,
    bind_dir: Optional[Path] = None,
    paths: Optional[Sequence[Path]] = None,
) -> Dict[str, object]:
    """Hash handwritten scans. Does not invent index rows or OCR text."""
    token = packet_id.strip()
    if not token or "\n" in token:
        raise HandwrittenScanError("packet_id must be a single-line string")
    if paths and bind_dir is None:
        raise HandwrittenScanError("paths requires bind-dir")
    pages: List[Dict[str, object]] = []
    bind_text = ""
    if bind_dir is not None:
        resolved = bind_dir.expanduser().resolve()
        if not resolved.is_dir():
            raise HandwrittenScanError(f"bind-dir is not a directory: {resolved}")
        bind_text = str(resolved)
        files: List[Path]
        if paths:
            files = []
            for raw in paths:
                scan = raw.expanduser().resolve()
                if resolved not in scan.parents and scan != resolved:
                    raise HandwrittenScanError(
                        f"scan path escapes the bind directory: {scan}"
                    )
                if not scan.is_file():
                    continue
                if scan.suffix.casefold() not in SCAN_SUFFIXES:
                    continue
                files.append(scan)
            files = sorted(
                files,
                key=lambda path: str(path.relative_to(resolved)).casefold(),
            )
        else:
            files = _scan_files(resolved)
        for index, path in enumerate(files, start=1):
            pages.append(
                {
                    "page": index,
                    "path": str(path.relative_to(resolved)).replace("\\", "/"),
                    "source_sha256": sha256_file(path),
                }
            )
    draft = {
        "schema_id": DRAFT_SCHEMA_ID,
        "schema_version": DRAFT_SCHEMA_VERSION,
        "status": DRAFT_STATUS,
        "packet_id": token,
        "expected_page_count": len(pages),
        "pages": pages,
        "bind_dir": bind_text,
        "notes": [
            "UNAPPROVED_DRAFT cannot bind index_export",
            "Transcribe only text visible on the hashed handwritten scan",
            "Horizon does not OCR or invent legal, party, or date values",
        ],
    }
    dest = output.expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(draft, indent=2, sort_keys=True), encoding="utf-8")
    return draft


def handwritten_scan_queue_from_draft(draft: Dict[str, object]) -> Dict[str, object]:
    """List hashed scans that still need a Penterra workbook export."""
    if not isinstance(draft, dict) or draft.get("schema_id") != DRAFT_SCHEMA_ID:
        raise HandwrittenScanError("handwritten-scan draft schema is invalid")
    pages = draft.get("pages")
    if not isinstance(pages, list):
        raise HandwrittenScanError("pages must be a list")
    items: List[Dict[str, object]] = []
    for raw in pages:
        if not isinstance(raw, dict) or type(raw.get("page")) is not int:
            continue
        items.append(
            {
                "page": raw["page"],
                "path": raw.get("path") or "",
                "source_sha256": raw.get("source_sha256") or "",
                "action": "transcribe_to_penterra",
            }
        )
    token = draft.get("packet_id")
    return {
        "schema_id": QUEUE_SCHEMA_ID,
        "schema_version": QUEUE_SCHEMA_VERSION,
        "packet_id": token if isinstance(token, str) else "",
        "items": items,
        "notes": [
            "This queue does not invent legal, party, or date values",
            "Type visible face text into a Penterra xlsx, then rerun",
            "Do not treat filename classification as legal authority",
        ],
    }


def write_handwritten_scan_queue(
    draft: Dict[str, object],
    output: Path,
) -> Dict[str, object]:
    queue = handwritten_scan_queue_from_draft(draft)
    dest = output.expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(queue, indent=2, sort_keys=True), encoding="utf-8")
    return queue
