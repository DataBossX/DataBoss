"""``databossx discover`` — scan the Horizon/Penterra work roots.

Each first-level subdirectory of a discovery root is treated as a project.
Completed projects are skipped (recorded, not ranked). Everything else is
flagged for missing artifacts:

* ``no_ocr``    — source documents (pdf/tiff/images) exist but no OCR output
* ``no_report`` — no report workbook/document anywhere in the project
* ``no_qa``     — no QA/audit artifact or non-empty proofs folder

Projects are ranked: more missing artifacts and more recent activity sort
first. The registry is written to ``<root>/registry.json`` (stable pointer)
with a versioned snapshot under ``foundry_state/`` — Zero-Destruction.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .config import FoundryConfig
from .logs import utc_now_iso
from .versioned import versioned_write_json

log = logging.getLogger("databossx.discover")

SOURCE_DOC_EXTS = {".pdf", ".tif", ".tiff", ".png", ".jpg", ".jpeg"}
REPORT_EXTS = {".xlsx", ".xlsm", ".docx", ".pdf", ".csv"}
QA_EXTS = {".json", ".md", ".xlsx", ".txt", ".pdf"}
COMPLETE_MARKERS = {"complete", "complete.txt", "done", "done.txt", "delivered.txt"}
COMPLETE_STATUSES = {"complete", "completed", "done", "delivered"}
MAX_FILES_PER_PROJECT = 5000


@dataclass
class ProjectScan:
    name: str
    path: Path
    root: Path
    complete: bool = False
    missing: List[str] = field(default_factory=list)
    score: int = 0
    last_modified: Optional[str] = None
    files_seen: int = 0

    def as_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "path": str(self.path),
            "root": str(self.root),
            "complete": self.complete,
            "missing": self.missing,
            "score": self.score,
            "last_modified": self.last_modified,
            "files_seen": self.files_seen,
        }


def _is_complete(project_dir: Path) -> bool:
    status_file = project_dir / "STATUS.json"
    if status_file.is_file():
        try:
            data = json.loads(status_file.read_text(encoding="utf-8"))
            if str(data.get("status", "")).lower() in COMPLETE_STATUSES:
                return True
        except (json.JSONDecodeError, OSError):
            log.warning("unreadable STATUS.json in %s", project_dir)
    try:
        for child in project_dir.iterdir():
            if child.is_file() and child.name.lower() in COMPLETE_MARKERS:
                return True
    except OSError:
        pass
    return False


def scan_project(project_dir: Path, root: Path, now: Optional[float] = None) -> ProjectScan:
    scan = ProjectScan(name=project_dir.name, path=project_dir, root=root)
    scan.complete = _is_complete(project_dir)

    has_source_docs = False
    has_ocr = False
    has_report = False
    has_qa = False
    latest_mtime = 0.0
    seen = 0

    for path in project_dir.rglob("*"):
        if seen >= MAX_FILES_PER_PROJECT:
            log.warning("scan capped at %d files in %s", MAX_FILES_PER_PROJECT, project_dir)
            break
        try:
            if path.is_dir():
                if path.name.lower() in ("ocr", "ocr_output"):
                    has_ocr = True
                continue
            if not path.is_file():
                continue
            seen += 1
            mtime = path.stat().st_mtime
        except OSError:
            continue
        latest_mtime = max(latest_mtime, mtime)
        ext = path.suffix.lower()
        stem = path.stem.lower()
        parts = {p.lower() for p in path.parts}

        if ext in SOURCE_DOC_EXTS:
            has_source_docs = True
        if "ocr" in stem or "ocr" in parts:
            has_ocr = True
        if ext == ".txt" and path.with_suffix(".pdf").exists():
            has_ocr = True  # text sidecar of a scanned pdf
        if "report" in stem and ext in REPORT_EXTS:
            has_report = True
        if ("qa" in stem.split("_") or stem.startswith("qa") or "audit" in stem) and ext in QA_EXTS:
            has_qa = True
        if ("proofs" in parts or "qa" in parts) and ext in QA_EXTS:
            has_qa = True

    scan.files_seen = seen
    if latest_mtime:
        scan.last_modified = _dt.datetime.fromtimestamp(
            latest_mtime, tz=_dt.timezone.utc
        ).isoformat(timespec="seconds")

    if not scan.complete:
        if has_source_docs and not has_ocr:
            scan.missing.append("no_ocr")
        if not has_report:
            scan.missing.append("no_report")
        if not has_qa:
            scan.missing.append("no_qa")

    # Rank: each missing artifact weighs 10; recent activity adds urgency.
    score = len(scan.missing) * 10
    if latest_mtime and now is not None:
        age_days = max(0.0, (now - latest_mtime) / 86400.0)
        if age_days <= 30:
            score += 3
        elif age_days <= 90:
            score += 1
    scan.score = score
    return scan


def discover(
    config: FoundryConfig,
    roots: Optional[Sequence[Path]] = None,
    now: Optional[float] = None,
) -> Dict[str, object]:
    if now is None:
        now = _dt.datetime.now(_dt.timezone.utc).timestamp()
    roots = tuple(roots) if roots else config.discover_roots
    ranked: List[ProjectScan] = []
    skipped: List[ProjectScan] = []
    root_states: List[Dict[str, object]] = []

    for root in roots:
        root = Path(root)
        exists = root.is_dir()
        root_states.append({"path": str(root), "exists": exists})
        if not exists:
            log.warning("discovery root does not exist: %s", root)
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            scan = scan_project(child, root, now=now)
            (skipped if scan.complete else ranked).append(scan)

    # Highest score first; among equals, most recent activity first.
    ranked.sort(key=lambda s: s.last_modified or "", reverse=True)
    ranked.sort(key=lambda s: s.score, reverse=True)
    registry: Dict[str, object] = {
        "generated_at": utc_now_iso(),
        "roots": root_states,
        "projects": [s.as_dict() for s in ranked],
        "skipped_complete": [s.as_dict() for s in skipped],
    }
    return registry


def write_registry(config: FoundryConfig, registry: Dict[str, object],
                   out: Optional[Path] = None) -> Tuple[Path, Path]:
    """Write the stable ``registry.json`` plus a versioned snapshot."""
    out = Path(out) if out else config.root / "registry.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    snapshot = versioned_write_json(config.state_dir, "registry", registry)
    out.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    return out, snapshot
