"""Drive the extraction pipeline from ingested notice-list rows.

A notice list (DSU / OFFSET) tells you WHICH sections/owners to research; it does
not usually contain the full instrument text. So the driver takes a `resolver`
callable that, given a row, returns the document texts for that row. This cleanly
decouples the source of documents (inline text, a local corpus, or a live
WeldRecorderClient) from the extract->reason->persist pipeline.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from app import db
from workflows.extraction_pipeline import run_pipeline

Resolver = Callable[[Dict[str, Any]], List[Tuple[str, str]]]


def make_corpus_resolver(corpus_dir: Path | str, section_field: str = "section") -> Resolver:
    """Resolve documents from a local corpus laid out as <corpus>/<Section>/*.txt.

    Section names are sanitized (spaces/slashes -> underscore) to match folder
    names. Returns (path, text) tuples sorted by filename. Missing folders yield
    an empty list rather than raising, so unknown sections are simply 'no docs'.
    """
    base = Path(corpus_dir)

    def resolver(row: Dict[str, Any]) -> List[Tuple[str, str]]:
        section = str(row.get(section_field) or "").strip()
        folder = base / section.replace(" ", "_").replace("/", "_")
        if not folder.is_dir():
            return []
        return [(str(p), p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.txt"))]

    return resolver


def drive(
    rows: List[Dict[str, Any]],
    resolver: Resolver,
    owner_field: str = "owner",
    section_field: str = "section",
    default_section: str = "Sec 1",
    conn: Optional[sqlite3.Connection] = None,
) -> List[Dict[str, Any]]:
    own_conn = conn is None
    conn = conn or db.connect()
    results: List[Dict[str, Any]] = []
    try:
        for row in rows:
            owner = str(row.get(owner_field, "")).strip()
            section = str(row.get(section_field) or default_section).strip()
            docs = resolver(row)
            outcome = run_pipeline(docs, owner=owner, section=section, conn=conn)
            db.log_audit(conn, actor="notice_list_driver", action="section_processed",
                         target=f"{owner}/{section}", detail={"n_docs": len(docs)})
            results.append({
                "owner": owner, "section": section,
                "decision": outcome["decision"], "docs": outcome["extracted"],
            })
        return results
    finally:
        if own_conn:
            conn.close()
