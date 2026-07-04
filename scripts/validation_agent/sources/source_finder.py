"""Locate source documents referenced by the workbook.

Search order: configured extra folders, the run's ``sources`` folder, then the
DataBossX documents/reports/workbooks trees. References (Book/Page, Instrument
Number, parties, wells, OGL, assignments) are parsed from the manifest. For
each reference the finder records exactly one status — found, missing, blocked,
or failed — and logs it. It never invents a document's contents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from config.settings import Settings
from core.hashing import sha256_file
from db.audit_logger import AuditLogger
from ingestion.sheet_classifier import ClassificationReport
from ingestion.workbook_ingestor import SheetView, WorkbookStructure
from sources.okcounty_client import OKCountyClient
from sources.source_cache import SourceCache
from validators.util import column_index, non_empty

_DOC_EXTS = {".pdf", ".tif", ".tiff", ".png", ".jpg", ".jpeg", ".docx", ".doc",
             ".txt", ".xml", ".json"}


@dataclass
class SourceReference:
    reference_key: str
    reference_type: str
    tokens: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reference_key": self.reference_key,
            "reference_type": self.reference_type,
            "tokens": self.tokens,
        }


def _norm_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text).lower())


def build_reference_queue(
    structure: WorkbookStructure, classification: ClassificationReport
) -> List[SourceReference]:
    refs: List[SourceReference] = []
    seen: Set[str] = set()

    def _add(key: str, rtype: str, tokens: List[str]) -> None:
        if not key or key in seen:
            return
        seen.add(key)
        refs.append(SourceReference(reference_key=key, reference_type=rtype, tokens=tokens))

    cats = {c.sheet_name: c.category for c in classification.classifications}
    for sheet in structure.sheets:
        cat = cats.get(sheet.name, "unknown")
        book = column_index(sheet.headers, "book", "volume", "vol")
        page = column_index(sheet.headers, "page", "pg")
        instr = column_index(sheet.headers, "instrument", "instrument number",
                             "recording number", "document number")
        well = column_index(sheet.headers, "well", "well name", "api")
        ogl = column_index(sheet.headers, "ogl", "lease number", "lease id")
        for row in sheet.rows:
            def _cell(idx: Optional[int]) -> Optional[str]:
                if idx is None or idx >= len(row) or not non_empty(row[idx]):
                    return None
                return str(row[idx]).strip()

            b, p = _cell(book), _cell(page)
            if b and p:
                _add(f"book_{_norm_token(b)}_page_{_norm_token(p)}", "book_page",
                     [_norm_token(b), _norm_token(p)])
            i = _cell(instr)
            if i:
                _add(f"instrument_{_norm_token(i)}", "instrument", [_norm_token(i)])
            w = _cell(well)
            if w:
                _add(f"well_{_norm_token(w)}", "well", [_norm_token(w)])
            o = _cell(ogl)
            if o:
                _add(f"ogl_{_norm_token(o)}", "ogl", [_norm_token(o)])
    return refs


@dataclass
class SourceIndex:
    found: List[Dict[str, Any]] = field(default_factory=list)
    missing: List[Dict[str, Any]] = field(default_factory=list)
    blocked: List[Dict[str, Any]] = field(default_factory=list)
    failed: List[Dict[str, Any]] = field(default_factory=list)
    contradictory: List[Dict[str, Any]] = field(default_factory=list)
    checked_dirs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "found": self.found,
            "missing": self.missing,
            "blocked": self.blocked,
            "failed": self.failed,
            "contradictory": self.contradictory,
            "found_keys": [f["reference_key"] for f in self.found],
            "checked_dirs": self.checked_dirs,
        }


class SourceFinder:
    def __init__(
        self,
        settings: Settings,
        audit: AuditLogger,
        cache: SourceCache,
        okcounty: Optional[OKCountyClient] = None,
        run_id: Optional[str] = None,
        run_sources_dir: Optional[Path] = None,
    ) -> None:
        self.settings = settings
        self.audit = audit
        self.cache = cache
        self.okcounty = okcounty
        self.run_id = run_id
        self.run_sources_dir = run_sources_dir

    def _search_dirs(self) -> List[Path]:
        dirs: List[Path] = []
        if self.run_sources_dir:
            dirs.append(Path(self.run_sources_dir))
        dirs.extend(self.settings.source_search_dirs())
        return [d for d in dirs if d.exists() and d.is_dir()]

    def _index_files(self, dirs: List[Path]) -> List[Path]:
        files: List[Path] = []
        for d in dirs:
            for path in d.rglob("*"):
                if path.is_file() and path.suffix.lower() in _DOC_EXTS:
                    files.append(path)
        return files

    def _match(self, ref: SourceReference, files: List[Path]) -> Optional[Path]:
        # Match on the full normalized reference key (e.g. "book101page201") so
        # short numeric tokens can never false-match unrelated files. A file is
        # a source only if its name carries the whole reference key, or every
        # token AND at least one token is distinctive (length >= 4).
        key = _norm_token(ref.reference_key)
        distinctive = any(len(t) >= 4 for t in ref.tokens)
        for path in files:
            name = _norm_token(path.stem)
            if key and key in name:
                return path
            if distinctive and ref.tokens and all(t and t in name for t in ref.tokens):
                return path
        return None

    def find(self, references: List[SourceReference]) -> SourceIndex:
        index = SourceIndex()
        dirs = self._search_dirs()
        index.checked_dirs = [str(d) for d in dirs]
        files = self._index_files(dirs)

        for ref in references:
            match = self._match(ref, files)
            if match is not None:
                sha = sha256_file(match)
                self.cache.add(ref.reference_key, ref.reference_type, match, "local")
                self.audit.log_source_document(
                    status="found",
                    reference_key=ref.reference_key,
                    reference_type=ref.reference_type,
                    file_path=str(match),
                    sha256=sha,
                    source="local",
                    run_id=self.run_id,
                )
                index.found.append(
                    {**ref.to_dict(), "file_path": str(match), "sha256": sha}
                )
                continue

            # Not local: try authorized retrieval only if live mode + client.
            if self.okcounty is not None and self.settings.live_source_mode:
                result = self.okcounty.fetch_document(ref.reference_key)
                if result.outcome == "retrieved" and result.file_path:
                    index.found.append({**ref.to_dict(), "file_path": result.file_path})
                    continue
                if result.outcome == "blocked":
                    self.audit.log_source_document(
                        status="blocked", reference_key=ref.reference_key,
                        reference_type=ref.reference_type, detail=result.detail,
                        source="api", run_id=self.run_id,
                    )
                    index.blocked.append({**ref.to_dict(), "detail": result.detail})
                    continue
                if result.outcome in ("auth_failure", "not_configured"):
                    self.audit.log_source_document(
                        status="failed", reference_key=ref.reference_key,
                        reference_type=ref.reference_type, detail=result.detail,
                        source="api", run_id=self.run_id,
                    )
                    index.failed.append({**ref.to_dict(), "detail": result.detail})
                    continue

            # Default: missing (checked, not found, not fabricated).
            self.audit.log_source_document(
                status="missing",
                reference_key=ref.reference_key,
                reference_type=ref.reference_type,
                detail=f"not found in {len(dirs)} search dir(s)",
                run_id=self.run_id,
            )
            index.missing.append({**ref.to_dict()})
        return index
