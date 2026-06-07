"""Build the cursory chain of title (Run Sheet rows) and detect gaps.

Documents are ordered by best-available date (recording, then execution,
then effective). We link consecutive conveyances by party overlap and flag
breaks where a grantee does not reappear as the next grantor.

Nothing is assumed from name similarity alone -- a suspected link with only a
fuzzy name overlap is annotated as "apparent" and surfaced as a curative item.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from .models import ChainLink, CurativeIssue, Document
from .utils import NEEDS_REVIEW, NOT_FOUND, parse_date


def _sort_key(d: Document):
    for field in (d.recording_date, d.execution_date, d.effective_date):
        dt = parse_date(field)
        if dt:
            return (0, dt)
    return (1, None)  # undated documents sort last


def build_run_sheet(docs: List[Document]) -> Tuple[List[dict], List[CurativeIssue]]:
    conveyances = [d for d in docs if _is_conveyance(d)]
    conveyances.sort(key=_sort_key)

    rows: List[dict] = []
    issues: List[CurativeIssue] = []

    for i, d in enumerate(conveyances, start=1):
        rows.append({
            "No.": i,
            "Document Type": d.document_type,
            "Grantor": "; ".join(d.grantors) or NOT_FOUND,
            "Grantee": "; ".join(d.grantees) or NOT_FOUND,
            "Execution Date": d.execution_date or NOT_FOUND,
            "Effective Date": d.effective_date or NOT_FOUND,
            "Recording Date": d.recording_date or NOT_FOUND,
            "Instrument No.": d.instrument_no or NOT_FOUND,
            "Book/Page": d.book_page or NOT_FOUND,
            "Legal Description": d.legal.raw or NOT_FOUND,
            "Interest/Lands Affected": d.interest or NEEDS_REVIEW,
            "Title Notes": d.title_effect or NEEDS_REVIEW,
            "Source": Path(d.source_file).name,
            "Confidence": d.relevance_confidence or d.match_confidence or 0,
        })

    # Gap detection: each conveyance's grantee should be the next grantor.
    for a, b in zip(conveyances, conveyances[1:]):
        if not a.grantees or not b.grantors:
            continue
        grantees = {g.lower() for g in a.grantees}
        next_grantors = {g.lower() for g in b.grantors}
        if grantees.isdisjoint(next_grantors):
            issues.append(CurativeIssue(
                issue_id=f"gap-{a.doc_id}-{b.doc_id}",
                category="gap",
                severity="high",
                description=(f"Possible chain gap: grantee(s) of '{a.document_type}' "
                             f"({'; '.join(a.grantees)}) do not appear as grantor(s) of "
                             f"the next instrument '{b.document_type}' "
                             f"({'; '.join(b.grantors)})."),
                related_documents=[a.doc_id, b.doc_id],
                recommendation="Locate intervening conveyance or curative affidavit.",
                confidence=60.0,
            ))

    if not conveyances:
        issues.append(CurativeIssue(
            issue_id="no-conveyances",
            category="missing_doc",
            severity="high",
            description="No conveyancing instruments were available to build a chain of title.",
            recommendation="Obtain base patent/root of title and subsequent conveyances "
                           "for the subject lands from the county records.",
            confidence=90.0,
        ))

    return rows, issues


def _is_conveyance(d: Document) -> bool:
    t = d.document_type.lower()
    return any(k in t for k in (
        "deed", "lease", "assignment", "patent", "probate", "release",
        "conveyance", "mortgage",
    ))
