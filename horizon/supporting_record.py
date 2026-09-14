"""Hash chat and OCR supporting records without treating them as legal fills.

Filename classification is not legal authority. Phase 1 live chat/OCR files
stay out unless the examiner copies them into sectionN-supporting/,
sectionN-chat/, or sectionN-ocr/. This is not package release.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .isolated_delta import sha256_file
from .source_acquisition import IMAGE_EXTENSIONS, classify_role

DRAFT_SCHEMA_ID = "dbx.supporting_record_draft"
DRAFT_SCHEMA_VERSION = "1.0"
DRAFT_STATUS = "UNAPPROVED_DRAFT"
QUEUE_SCHEMA_ID = "dbx.supporting_record_queue"
QUEUE_SCHEMA_VERSION = "1.0"
SUPPORT_ROLES = {"chat_export", "ocr_text", "supporting_record"}
SUPPORT_SUFFIXES = {
    ".csv",
    ".doc",
    ".docx",
    ".json",
    ".md",
    ".pdf",
    ".txt",
    *IMAGE_EXTENSIONS,
}


class SupportingRecordError(ValueError):
    """Raised when a supporting-record draft cannot be written safely."""


def _support_files(bind_dir: Path) -> List[Path]:
    try:
        children = list(bind_dir.iterdir())
    except OSError as exc:
        raise SupportingRecordError(f"Cannot read bind-dir: {exc}") from exc
    files = [
        path
        for path in children
        if path.is_file() and path.suffix.casefold() in SUPPORT_SUFFIXES
    ]
    return sorted(files, key=lambda path: path.name.casefold())


def _role_for(path: Path, bind: Path) -> str:
    relative = str(path.relative_to(bind)).replace("\\", "/")
    role = classify_role(relative, path.suffix.casefold())
    if role in {"chat_export", "ocr_text"}:
        return role
    parent = path.parent.name.casefold()
    if "chat" in parent or "slack" in parent:
        return "chat_export"
    if "ocr" in parent:
        return "ocr_text"
    return "supporting_record"


def write_supporting_record_draft(
    *,
    output: Path,
    packet_id: str,
    bind_dir: Optional[Path] = None,
    paths: Optional[Sequence[Path]] = None,
) -> Dict[str, object]:
    """Hash chat/OCR files. Does not invent legal, party, or date values."""
    token = packet_id.strip()
    if not token or "\n" in token:
        raise SupportingRecordError("packet_id must be a single-line string")
    if paths and bind_dir is None:
        raise SupportingRecordError("paths requires bind-dir")
    files_out: List[Dict[str, object]] = []
    bind_text = ""
    if bind_dir is not None:
        resolved = bind_dir.expanduser().resolve()
        if not resolved.is_dir():
            raise SupportingRecordError(f"bind-dir is not a directory: {resolved}")
        bind_text = str(resolved)
        selected: List[Path]
        if paths:
            selected = []
            for raw in paths:
                item = raw.expanduser().resolve()
                if resolved not in item.parents and item != resolved:
                    raise SupportingRecordError(
                        f"supporting path escapes the bind directory: {item}"
                    )
                if not item.is_file():
                    continue
                if item.suffix.casefold() not in SUPPORT_SUFFIXES:
                    continue
                selected.append(item)
            selected = sorted(
                selected,
                key=lambda path: str(path.relative_to(resolved)).casefold(),
            )
        else:
            selected = _support_files(resolved)
        for path in selected:
            files_out.append(
                {
                    "path": str(path.relative_to(resolved)).replace("\\", "/"),
                    "source_sha256": sha256_file(path),
                    "role": _role_for(path, resolved),
                }
            )
    draft = {
        "schema_id": DRAFT_SCHEMA_ID,
        "schema_version": DRAFT_SCHEMA_VERSION,
        "status": DRAFT_STATUS,
        "packet_id": token,
        "files": files_out,
        "bind_dir": bind_text,
        "notes": [
            "UNAPPROVED_DRAFT cannot bind isolated_delta or index_export",
            "Chat and OCR are review-only; they are not legal authority",
            "Do not copy chat or OCR text into legal, party, or date cells",
        ],
    }
    dest = output.expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(draft, indent=2, sort_keys=True), encoding="utf-8")
    return draft


def supporting_record_queue_from_draft(draft: Dict[str, object]) -> Dict[str, object]:
    """List hashed chat/OCR files for review. Does not invent fills."""
    if not isinstance(draft, dict) or draft.get("schema_id") != DRAFT_SCHEMA_ID:
        raise SupportingRecordError("supporting-record draft schema is invalid")
    files = draft.get("files")
    if not isinstance(files, list):
        raise SupportingRecordError("files must be a list")
    items: List[Dict[str, object]] = []
    for raw in files:
        if not isinstance(raw, dict):
            continue
        role = raw.get("role") if isinstance(raw.get("role"), str) else "supporting_record"
        items.append(
            {
                "path": raw.get("path") or "",
                "source_sha256": raw.get("source_sha256") or "",
                "role": role,
                "action": "review_only",
                "legal_authority": False,
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
            "Chat and OCR are not legal authority",
            "Do not copy supporting text into the isolated index",
        ],
    }


def write_supporting_record_queue(
    draft: Dict[str, object],
    output: Path,
) -> Dict[str, object]:
    queue = supporting_record_queue_from_draft(draft)
    dest = output.expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(queue, indent=2, sort_keys=True), encoding="utf-8")
    return queue
