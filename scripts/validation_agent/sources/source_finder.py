"""Source finder: builds the missing-document queue and locates sources.

Parses references out of the workbook/report, builds a queue of documents that
are needed but not yet on hand, searches local folders + prior run caches
first, and only escalates to live paid retrieval when explicitly enabled and
spend-approved. It never invents the contents of a document it cannot find.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# Reference extraction patterns.
_BOOK_PAGE_RE = re.compile(r"\b(?:bk\.?|book)\s*(\w+)[\s,/-]+(?:pg\.?|page)\s*(\w+)",
                           re.IGNORECASE)
_INSTRUMENT_RE = re.compile(r"\b(?:inst(?:rument)?\.?\s*(?:no\.?|#)?\s*)"
                            r"([0-9]{4,}[-0-9]*)", re.IGNORECASE)
_STR_RE = re.compile(r"\bS(?:ec)?\.?\s*(\d{1,2})[-\s,]+T(\d{1,2}[NS])"
                     r"[-\s,]+R(\d{1,2}[EW])", re.IGNORECASE)


@dataclass
class MissingSource:
    reference_key: str
    doc_type: str = "unknown"
    county: str = ""
    party_names: str = ""
    detail: dict = field(default_factory=dict)
    status: str = "missing"
    source_origin: str = "none"
    file_path: Optional[str] = None
    sha256: Optional[str] = None
    cost_usd: float = 0.0
    note: str = ""


def extract_references(text: str) -> list[dict]:
    """Extract book/page, instrument, and S-T-R references from free text."""
    refs: list[dict] = []
    seen: set[str] = set()
    for m in _BOOK_PAGE_RE.finditer(text or ""):
        key = f"bk {m.group(1)}/pg {m.group(2)}".lower()
        if key not in seen:
            seen.add(key)
            refs.append({"reference_key": key, "doc_type": "instrument",
                         "book": m.group(1), "page": m.group(2)})
    for m in _INSTRUMENT_RE.finditer(text or ""):
        key = f"inst {m.group(1)}".lower()
        if key not in seen:
            seen.add(key)
            refs.append({"reference_key": key, "doc_type": "instrument",
                         "instrument_number": m.group(1)})
    for m in _STR_RE.finditer(text or ""):
        key = f"s{m.group(1)}-t{m.group(2)}-r{m.group(3)}".lower()
        if key not in seen:
            seen.add(key)
            refs.append({"reference_key": key, "doc_type": "legal_description",
                         "section": m.group(1), "township": m.group(2),
                         "range": m.group(3)})
    return refs


class SourceFinder:
    def __init__(self, settings, run_dir: str | Path, db=None, run_id=None,
                 okcounty=None, cache=None):
        self.settings = settings
        self.run_dir = Path(run_dir)
        self.db = db
        self.run_id = run_id
        self.okcounty = okcounty
        self.cache = cache
        self.search_dirs = self._build_search_dirs()

    def _build_search_dirs(self) -> list[Path]:
        dirs = [
            self.run_dir / "sources",
            self.settings.project_root / "documents",
            self.settings.project_root / "sources",
            self.settings.outputs_dir,
        ]
        dirs.extend(self.settings.extra_source_dirs)
        return [d for d in dirs if d.exists()]

    def build_missing_queue(self, references: list[dict],
                            known_source_keys: set[str] | None = None
                            ) -> list[MissingSource]:
        """Turn extracted references into a queue of MissingSource items.

        Local folders and prior caches are searched first; anything not found
        locally is flagged 'missing' (candidate for queued/live retrieval).
        """
        known = {k.lower() for k in (known_source_keys or set())}
        queue: list[MissingSource] = []
        for ref in references:
            key = ref["reference_key"]
            if key.lower() in known:
                continue
            item = MissingSource(
                reference_key=key,
                doc_type=ref.get("doc_type", "unknown"),
                detail=ref,
            )
            local = self._search_local(key)
            if local:
                item.status = "found_local"
                item.source_origin = "local"
                item.file_path = str(local)
            queue.append(item)
        return queue

    def _search_local(self, reference_key: str) -> Path | None:
        if self.cache:
            hit = self.cache.find_local(reference_key)
            if hit:
                return hit
        safe = re.sub(r"[^a-z0-9]+", "*", reference_key.lower()).strip("*")
        if not safe:
            return None
        for d in self.search_dirs:
            for p in d.rglob(f"*{safe}*"):
                if p.is_file():
                    return p
        return None

    def persist_queue(self, queue: list[MissingSource]) -> None:
        if not self.db or not self.run_id:
            return
        for item in queue:
            self.db.record_source_document(
                self.run_id, reference_key=item.reference_key,
                doc_type=item.doc_type, county=item.county,
                party_names=item.party_names, status=item.status,
                source_origin=item.source_origin, file_path=item.file_path,
                sha256=item.sha256, cost_usd=item.cost_usd, note=item.note,
            )

    def attempt_live_retrieval(self, queue: list[MissingSource],
                               examiner_approved: bool = False
                               ) -> list[MissingSource]:
        """For still-missing items, try live retrieval IF enabled+approved.

        In dry-run or when OKCounty is unavailable, items are marked 'queued'
        (nothing is fabricated). Spend is always enforced by the guard inside
        the client.
        """
        if not (self.okcounty and self.okcounty.is_available()):
            for item in queue:
                if item.status == "missing":
                    item.status = "queued"
                    item.note = "Live source disabled or credentials absent."
            return queue
        for item in queue:
            if item.status != "missing":
                continue
            result = self.okcounty.search(item.reference_key, item.county,
                                          item.doc_type)
            if not result:
                item.status = "queued"
                item.note = "Not found or search blocked; escalated."
                continue
            retrieved = self.okcounty.retrieve(
                result, self.cache, examiner_approved=examiner_approved
            )
            if retrieved:
                path, digest, cost = retrieved
                item.status = "retrieved"
                item.source_origin = "okcounty"
                item.file_path = str(path)
                item.sha256 = digest
                item.cost_usd = float(cost)
            else:
                item.status = "blocked"
                item.note = "Retrieval blocked by spend cap or policy."
        return queue
