"""Offline MOCK OCR provider for DataBossX preflight.

⚠️ This does NOT read images and is NOT a real extraction. It returns
schema-valid synthetic results so the gated pipeline can be proven end-to-end
with zero cost and zero network/browser dependency. Real OCR (Gemini, etc.)
plugs in behind the same interface and MUST pass the cost guard first.

To exercise the gates it deliberately produces a mix:
  * matching high-confidence rows
  * a low-confidence row (-> Needs Human Review)
  * a mismatching row (-> caught by row_compare)
"""
from __future__ import annotations

from . import document_schema as schema


def extract(workbook_row: dict, row_index: int) -> dict:
    """Return a schema-valid MOCK result keyed off the workbook row."""
    r = schema.blank_result()
    r["instrument_type"] = workbook_row.get("Instrument_Type")
    r["document_date"] = workbook_row.get("Document_Date")
    r["recorded_date"] = workbook_row.get("Recorded_Date")
    r["book"] = str(workbook_row.get("Book")) if workbook_row.get("Book") is not None else None
    r["page"] = str(workbook_row.get("Page")) if workbook_row.get("Page") is not None else None
    r["grantors"] = [workbook_row["Grantor"]] if workbook_row.get("Grantor") else []
    r["grantees"] = [workbook_row["Grantee"]] if workbook_row.get("Grantee") else []
    r["legal_descriptions"] = [workbook_row["Legal_Description"]] if workbook_row.get("Legal_Description") else []
    r["confidence"] = 0.93
    r["visible_evidence"] = ["MOCK OCR — synthetic evidence derived from runsheet row"]
    r["notes"] = "MOCK OCR result — not a real extraction"

    # Row 2 (index 1): simulate low confidence -> Needs Human Review.
    if row_index == 1:
        r["confidence"] = 0.40
        r["uncertain_fields"] = ["recorded_date"]
    # Row 3 (index 2): simulate an OCR/workbook disagreement on Book.
    if row_index == 2:
        r["book"] = "9999"

    return r
