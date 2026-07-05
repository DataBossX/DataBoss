"""Scan local folders (and optionally Google Drive) for Section 31 files.

Local-first: the local filesystem is always scanned. Google Drive is a
*fallback* -- consulted only when credentials are present and either the local
scan came up short or the operator asks for it. Both return the same
:class:`Candidate` shape so downstream ranking is source-agnostic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .config import Section31Config

# What "looks like a Section 31 file" -- tokens we expect in a relevant name.
_SECTION_TOKENS = [
    r"sec(?:tion)?[\s._-]*31\b",
    r"\b31[\s._-]*12n[\s._-]*24w\b",
    r"12n[\s._-]*24w",
    r"roger[\s._-]*mills",
]
_SECTION_RE = re.compile("|".join(_SECTION_TOKENS), re.IGNORECASE)

_WORKBOOK_EXT = {".xlsx", ".xlsm", ".xls"}
_RUNSHEET_HINT = re.compile(r"run[\s._-]*sheet|runsheet|abstract|ogl|lease", re.I)
_IMAGE_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


@dataclass
class Candidate:
    """A file the scanner thinks might feed the Section 31 report."""

    name: str
    path: str            # local path or drive:<id>
    source: str          # "local" | "drive"
    kind: str            # "workbook" | "runsheet" | "image" | "other"
    size: int = 0
    modified: float = 0.0
    drive_id: Optional[str] = None
    section_match: bool = False
    notes: List[str] = field(default_factory=list)

    @property
    def ext(self) -> str:
        return Path(self.name).suffix.lower()


def _classify(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext in _WORKBOOK_EXT:
        return "runsheet" if _RUNSHEET_HINT.search(name) else "workbook"
    if ext in _IMAGE_EXT:
        return "image"
    return "other"


def scan_local(cfg: Section31Config, extra_roots: Optional[List[Path]] = None) -> List[Candidate]:
    """Walk the Roger Mills root (and any extra roots) for candidate files.

    The app's own managed subfolders are skipped so we never re-ingest our own
    output -- except ``_candidate_workbooks`` which is *meant* to hold inputs.
    """
    roots = [cfg.root]
    if extra_roots:
        roots.extend(Path(r) for r in extra_roots)

    found: List[Candidate] = []
    seen = set()
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            # Skip our own outputs, but keep the candidate-inbox folder.
            if cfg.is_managed(path) and cfg.candidates_dir not in path.parents:
                continue
            if path == cfg.final_workbook:
                continue
            kind = _classify(path.name)
            if kind == "other":
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            try:
                stat = path.stat()
                size, mtime = stat.st_size, stat.st_mtime
            except OSError:
                size, mtime = 0, 0.0
            found.append(
                Candidate(
                    name=path.name,
                    path=str(path),
                    source="local",
                    kind=kind,
                    size=size,
                    modified=mtime,
                    section_match=bool(_SECTION_RE.search(path.name)),
                )
            )
    return found


def scan_drive(cfg: Section31Config, drive_client, query_folder: Optional[str] = None) -> List[Candidate]:
    """Fallback scan of Google Drive via an injected client.

    ``drive_client`` must expose ``list_files(name_contains=...) ->
    [{'id','name','mimeType','size','modifiedTime'}]``. If the client is None
    or errors, an empty list is returned (local-first: Drive is optional).
    """
    if drive_client is None:
        return []
    out: List[Candidate] = []
    try:
        entries = drive_client.list_files(name_contains="31") or []
    except Exception:
        return []
    for e in entries:
        name = e.get("name", "")
        if not _SECTION_RE.search(name):
            continue
        kind = _classify(name)
        if kind == "other":
            continue
        out.append(
            Candidate(
                name=name,
                path=f"drive:{e.get('id','')}",
                source="drive",
                kind=kind,
                size=int(e.get("size") or 0),
                drive_id=e.get("id"),
                section_match=True,
                notes=["from Google Drive fallback"],
            )
        )
    return out


def scan_all(
    cfg: Section31Config,
    extra_roots: Optional[List[Path]] = None,
    drive_client=None,
    use_drive: bool = False,
) -> List[Candidate]:
    """Local-first scan; consult Drive only when asked or when local is thin."""
    local = scan_local(cfg, extra_roots)
    workbooks = [c for c in local if c.kind in ("workbook", "runsheet")]
    if use_drive or not workbooks:
        local.extend(scan_drive(cfg, drive_client))
    return local
