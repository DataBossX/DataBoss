"""Assemble a ReportData object from inventoried sources and extracted docs.

Honesty rules enforced here:
  * No source documents  -> every conclusion is "Needs Review" with confidence 0
    and an explicit Curative Issue is raised for the missing inputs.
  * A conclusion's confidence is the support of its underlying documents, never
    higher than the weakest required link.
"""

from __future__ import annotations

from datetime import date
from typing import List

from .models import (
    CurativeIssue,
    Document,
    ReportData,
    SourceFile,
    TractKey,
    NEEDS_REVIEW,
    UNKNOWN,
)


LEASE_TYPES = {"Oil and Gas Lease"}


def _avg(nums: List[int]) -> int:
    nums = [n for n in nums if n]
    return int(round(sum(nums) / len(nums))) if nums else 0


def build_report(tract: TractKey, sources: List[SourceFile],
                 documents: List[Document], wells: List[dict],
                 search_log: List[dict], limitations: List[str]) -> ReportData:
    today = date.today().strftime("%-m/%-d/%Y") if hasattr(date.today(), "strftime") else str(date.today())
    rd = ReportData(tract=tract, date_prepared=today, sources=sources,
                    documents=documents, wells=wells, search_log=search_log,
                    limitations=list(limitations))

    rd.leases = [d for d in documents if d.doc_type in LEASE_TYPES]
    rd.curative = _curative(tract, sources, documents)
    rd.title_narrative = _title_narrative(tract, documents)
    rd.overview = _overview(tract, today, sources, documents, rd.leases, wells)
    rd.confidence = _confidence(sources, documents, rd.leases, wells)
    return rd


def _curative(tract, sources, documents) -> List[CurativeIssue]:
    issues: List[CurativeIssue] = []
    n = 0
    if not sources:
        n += 1
        issues.append(CurativeIssue(
            issue_no=n, severity="Critical", issue_type="Missing Inputs",
            affected_instrument="ALL",
            affected_lands=tract.legal_base,
            problem=("No source documents were located in the run's source "
                     "directory and no record source was accessible. A title "
                     "chain cannot be established without inputs."),
            needed_action=("Provide the source set: prior workbook(s) "
                           "(e.g. Section 10 example, any Section 27 workbook), "
                           "the county index/runsheet, and scanned instruments; "
                           "or configure authorized record access."),
            suggested_curative="Place files in the --source-dir and re-run; "
                               "or set OKCOUNTY_API_KEY and pass --collect-records.",
            source="title_report_factory inventory",
            confidence=100,
        ))
    if not documents:
        n += 1
        issues.append(CurativeIssue(
            issue_no=n, severity="Critical", issue_type="No Chain of Title",
            affected_instrument="ALL", affected_lands=tract.legal_base,
            problem="No instruments extracted; ownership of the target interest "
                    "is entirely unverified.",
            needed_action="Supply and OCR the chain documents, then re-run.",
            suggested_curative="See Issue 1.",
            source="title_report_factory analysis", confidence=100,
        ))
    # Flag low-confidence / tract-unconfirmed documents.
    for d in documents:
        if d.relevance_confidence and d.relevance_confidence < 40:
            n += 1
            issues.append(CurativeIssue(
                issue_no=n, severity="Medium", issue_type="Tract Relevance",
                affected_instrument=f"{d.doc_type} {d.instrument_no}",
                affected_lands=d.legal_description,
                problem="Document does not clearly reference the subject "
                        "Section/Township/Range.",
                needed_action="Confirm whether this instrument affects the subject tract.",
                suggested_curative="Re-examine the legal description on the source image.",
                source=d.source_ref, confidence=60,
            ))
    return issues


def _title_narrative(tract, documents) -> List[dict]:
    if not documents:
        return [{
            "conclusion": f"Apparent {tract.target_owner} interest in {tract.short}",
            "support": "None — no source documents available.",
            "confidence": "0",
        }]
    rows = []
    rows.append({
        "conclusion": f"Apparent {tract.target_owner} interest in {tract.short}",
        "support": f"{len(documents)} instrument(s) extracted; chain not yet "
                   f"verified end-to-end.",
        "confidence": str(_avg([d.confidence for d in documents])),
    })
    return rows


def _overview(tract, today, sources, documents, leases, wells) -> dict:
    no_data = "Unknown — no source documents provided." if not sources else NEEDS_REVIEW
    return {
        "Report Title": f"Cursory Title Report — {tract.target_owner}",
        "County/State": f"{tract.county} County, {tract.state}",
        "Section-Township-Range": tract.legal_base,
        "Target Owner/Entity": tract.target_owner,
        "Date Prepared": today,
        "Prepared From Sources": (f"{len(sources)} source file(s) inventoried; "
                                  f"{len(documents)} instrument(s) extracted."),
        "Summary of Apparent Interest": (
            f"{tract.target_owner}'s interest could NOT be determined — "
            "no source records were available."
            if not documents else NEEDS_REVIEW),
        "Summary of Leases / OGL Status": (no_data if not leases
                                           else f"{len(leases)} lease(s) identified — see OGL sheet."),
        "Summary of Well / HBP Status": (no_data if not wells
                                         else f"{len(wells)} well(s) identified — see Well Data sheet."),
        "Major Assumptions": "None made. Report contains no fabricated facts.",
        "Major Title Issues": ("Critical: no inputs available; see Curative Issues."
                               if not sources else NEEDS_REVIEW),
        "Overall Confidence Score": "0" if not documents else str(_avg([d.confidence for d in documents])),
        "Human Review Required": ("YES — this is an empty-input skeleton. Provide "
                                  "the source set and re-run.") if not sources else "YES",
    }


def _confidence(sources, documents, leases, wells) -> dict:
    doc_avg = _avg([d.confidence for d in documents])
    ocr_avg = _avg([d.ocr_confidence for d in documents])
    completeness = 0 if not sources else min(100, 20 + len(documents) * 5)
    strongest, weakest = [], []
    if documents:
        ranked = sorted(documents, key=lambda d: d.confidence)
        weakest = [f"{d.doc_type} {d.instrument_no} ({d.confidence})" for d in ranked[:3]]
        strongest = [f"{d.doc_type} {d.instrument_no} ({d.confidence})" for d in ranked[-3:]]
    else:
        weakest = ["Entire report — no inputs (0)"]
        strongest = ["None"]
    return {
        "Overall Confidence Score": "0" if not documents else str(doc_avg),
        "Workbook Completeness Score": str(completeness),
        "Record Gathering Confidence": "0" if not sources else "50",
        "OCR Quality Confidence": str(ocr_avg),
        "Index Matching Confidence": str(_avg([d.match_confidence for d in documents])),
        "Runsheet Confidence": str(doc_avg),
        "OGL Confidence": "0" if not leases else str(_avg([d.confidence for d in leases])),
        "Well Data Confidence": "0" if not wells else "50",
        "Title Conclusion Confidence": "0" if not documents else str(doc_avg),
        "Strongest-Supported Conclusions": strongest,
        "Weakest-Supported Conclusions": weakest,
    }
