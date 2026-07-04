"""
Source finder.

Parses a workbook (and optional report text) for recorded-instrument references,
builds a missing-source queue, searches local folders / the run cache first, and
only then queues OKCounty retrieval (live mode). Blocked or unfound documents go
to escalation. Document contents are NEVER invented.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import Settings
from db.db_client import DatabaseManager, utcnow
from sources.source_cache import SourceCache
from validators.wb_access import find_book_page_refs


@dataclass
class MissingItem:
    reference: str
    kind: str
    sheet: str
    cell: str
    status: str = "missing"           # missing / found_local / retrieved / blocked / unverifiable
    file_path: Optional[str] = None
    source: Optional[str] = None


@dataclass
class SourceQueue:
    items: List[MissingItem] = field(default_factory=list)

    @property
    def missing(self) -> List[MissingItem]:
        return [i for i in self.items if i.status == "missing"]

    @property
    def resolved(self) -> List[MissingItem]:
        return [i for i in self.items if i.status in ("found_local", "retrieved")]


class SourceFinder:
    def __init__(self, db: DatabaseManager, settings: Settings, cache: SourceCache,
                 run_id: Optional[str] = None, search_dirs: Optional[List[str]] = None):
        self.db = db
        self.settings = settings
        self.cache = cache
        self.run_id = run_id
        self.search_dirs = [Path(d) for d in (search_dirs or [])]

    def build_queue(self, workbook_path: str) -> SourceQueue:
        refs = find_book_page_refs(workbook_path)
        q = SourceQueue()
        for r in refs:
            item = MissingItem(reference=r["reference"], kind=r["kind"],
                               sheet=r.get("sheet", ""), cell=r.get("cell", ""))
            # Search local folders + cache first.
            hit = self.cache.find_local(item.reference, self.search_dirs + [self.cache.cache_dir])
            if hit:
                item.status = "found_local"
                item.file_path = hit["path"]
                item.source = hit["source"] if "source" in hit else "cache"
            q.items.append(item)
            self._persist(item)
        return q

    def _persist(self, item: MissingItem) -> None:
        self.db.insert("source_documents", {
            "run_id": self.run_id, "doc_kind": item.kind, "reference": item.reference,
            "description": f"{item.kind} referenced at {item.sheet}!{item.cell}",
            "status": item.status, "file_path": item.file_path, "sha256": None,
            "source": item.source, "created_at": utcnow(),
        })

    def summary(self, q: SourceQueue) -> Dict[str, int]:
        return {
            "total": len(q.items),
            "missing": len(q.missing),
            "found_local": len(q.resolved),
        }
