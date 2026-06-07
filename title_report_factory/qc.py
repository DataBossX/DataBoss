"""The four required quality-control passes.

Each pass returns a dict {pass, result, detail} appended to ReportData.qc_results
and rendered onto the Confidence Summary sheet. The Excel Final Check is run
separately after the file is written (see workbook.verify_workbook).
"""

from __future__ import annotations

from typing import List

from .models import ReportData


def source_completeness_check(rd: ReportData) -> dict:
    if not rd.sources:
        return {"pass": "Source Completeness Check", "result": "FAIL (no inputs)",
                "detail": "0 source files inventoried. Nothing to process; "
                          "all data sheets are empty skeletons by design."}
    processed = sum(1 for s in rd.sources if s.extraction_status != "Pending")
    return {"pass": "Source Completeness Check",
            "result": "PASS" if processed == len(rd.sources) else "PARTIAL",
            "detail": f"{processed}/{len(rd.sources)} source files processed."}


def ocr_extraction_check(rd: ReportData) -> dict:
    ocr_sources = [s for s in rd.sources if s.source_type in ("PDF", "Image")]
    if not ocr_sources:
        return {"pass": "OCR and Extraction Check", "result": "N/A",
                "detail": "No scanned PDFs or images present to OCR."}
    ok = sum(1 for s in ocr_sources if s.ocr_status not in ("Pending", "no-engine", "error"))
    return {"pass": "OCR and Extraction Check",
            "result": "PASS" if ok == len(ocr_sources) else "PARTIAL",
            "detail": f"{ok}/{len(ocr_sources)} scanned files produced OCR text."}


def title_logic_check(rd: ReportData) -> dict:
    if not rd.documents:
        return {"pass": "Title Logic Check", "result": "FAIL (no chain)",
                "detail": "No instruments; chain gaps cannot even be evaluated. "
                          "Target-owner interest is UNVERIFIED."}
    gaps = sum(1 for d in rd.documents if d.relevance_confidence < 40)
    return {"pass": "Title Logic Check",
            "result": "REVIEW" if gaps else "PASS",
            "detail": f"{gaps} instrument(s) with unconfirmed tract relevance; "
                      f"{len(rd.documents)} total instruments."}


def run_all(rd: ReportData) -> List[dict]:
    rd.qc_results = [
        source_completeness_check(rd),
        ocr_extraction_check(rd),
        title_logic_check(rd),
    ]
    return rd.qc_results
