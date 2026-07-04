"""Source finder — builds a missing-document queue and searches local folders
first, then configured directories, then (only if live) OKCountyRecords.

It never invents document contents. Anything not lawfully/safely retrievable is
logged and pushed to the escalation queue.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import Settings
from db.audit_logger import AuditLogger
from sources.okcounty_client import OKCountyClient

BOOK_PAGE_RE = re.compile(r"\b(\d{3,4})\s*[/-]\s*(\d{1,4})\b")
INSTRUMENT_RE = re.compile(r"\b(\d{4}-\d{5,6})\b")


def parse_references(text: str) -> Dict[str, List[str]]:
    return {
        "book_page": sorted({f"{m.group(1)}/{m.group(2)}" for m in BOOK_PAGE_RE.finditer(text)}),
        "instrument_number": sorted({m.group(1) for m in INSTRUMENT_RE.finditer(text)}),
    }


class SourceFinder:
    def __init__(self, settings: Settings, audit: AuditLogger, client: OKCountyClient,
                 run_id: str, search_dirs: Optional[List[Path]] = None):
        self.settings = settings
        self.audit = audit
        self.client = client
        self.run_id = run_id
        self.search_dirs = list(search_dirs or []) + list(settings.extra_source_dirs)

    def _find_local(self, ref: str) -> Optional[Path]:
        token = ref.replace("/", "_")
        for d in self.search_dirs:
            d = Path(d)
            if not d.exists():
                continue
            for p in d.rglob("*"):
                if p.is_file() and token in p.name.replace("/", "_"):
                    return p
        return None

    def build_and_resolve_queue(self, references: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for kind in ("book_page", "instrument_number"):
            for ref in references.get(kind, []):
                local = self._find_local(ref)
                if local is not None:
                    rec = {"book_page": ref if kind == "book_page" else None,
                           "instrument_number": ref if kind == "instrument_number" else None,
                           "status": "found_local", "origin": "local",
                           "local_path": str(local), "detail": "matched by reference in filename"}
                else:
                    # Not local. In dry-run this stays queued/blocked; never invented.
                    outcome = self.client.retrieve_document(ref, self.settings.per_doc_limit_usd)
                    status = "found_local" if outcome.get("status") == "retrieved" else "blocked"
                    rec = {"book_page": ref if kind == "book_page" else None,
                           "instrument_number": ref if kind == "instrument_number" else None,
                           "status": "queued" if outcome.get("status") == "blocked" else status,
                           "origin": "okcounty", "local_path": None,
                           "detail": outcome.get("reason", "not retrieved")}
                self.audit.source_document(dict(rec, run_id=self.run_id))
                if rec["status"] in ("queued", "blocked", "unavailable"):
                    self.audit.escalate(self.run_id, {
                        "failure_class": "Missing Source",
                        "subject": ref,
                        "reason": "Source document could not be retrieved in this environment.",
                        "needed_document": ref,
                        "recommended_action": "Retrieve via authenticated OKCountyRecords or provide locally.",
                        "priority": "HIGH"})
                results.append(rec)
        return results
