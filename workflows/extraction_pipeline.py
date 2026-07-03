"""End-to-end extraction pipeline: text docs -> extract -> reason -> persist.

Ties the agents, guardrails, and DB together through the Workflow runner. Every
document extraction and the final decision are written to the DB as proof.
Runs fully offline when no LLM keys are present.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from agents.extractor import ExtractorAgent
from agents.reasoner import ReasonerAgent
from app import db
from workflows.runner import Workflow


def run_pipeline(
    documents: List[Tuple[str, str]],  # (source_path, untrusted_text)
    owner: str,
    section: str = "Sec 1",
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    """Process documents and return the ownership decision.

    documents: list of (source_path, text). Returns the reasoner decision dict.
    """
    own_conn = conn is None
    conn = conn or db.connect()
    extractor = ExtractorAgent()
    reasoner = ReasonerAgent()

    wf = Workflow("extraction_pipeline")

    def step_extract(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        extracted: List[Dict[str, Any]] = []
        for source_path, text in documents:
            doc_id = db.insert_document(conn, source_path=source_path, doc_type="county_instrument")
            fields = extractor.run(text, source_url=source_path)
            for name, value in fields.items():
                db.insert_extraction(conn, doc_id, name, value, model=extractor.model)
            db.log_audit(conn, actor="extractor", action="extracted", target=source_path,
                         detail={"legal_short": fields.get("legal_short")})
            extracted.append(fields)
        return extracted

    def step_reason(ctx: Dict[str, Any]) -> Dict[str, Any]:
        decision = reasoner.run(ctx["extract"], owner, section)
        db.log_audit(conn, actor="reasoner", action="decided", target=f"{owner}/{section}",
                     detail=decision)
        return decision

    wf.step("extract", step_extract).step("reason", step_reason)

    try:
        result = wf.run()
        if not result.ok:
            failed = next(r for r in result.results if not r.ok)
            raise RuntimeError(f"pipeline step '{failed.name}' failed: {failed.error}")
        return result.results[-1].value
    finally:
        if own_conn:
            conn.close()
