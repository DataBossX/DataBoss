"""Canonical schema for the Section 31 final workbook.

This module is the single source of truth for the sheets and columns the final
XLSX must contain. Every builder module (ownership, leasehold, wells, ...)
produces rows keyed to the column lists defined here, and the exporter writes
them out in this exact order. Keeping the schema in one place means QA and the
exporter can never drift apart.
"""

from __future__ import annotations

from typing import Dict, List

# Cover / provenance sheet (written as key/value rows, not a table).
COVER_SHEET = "Cover"

# Sheet name -> ordered column headers.
SHEETS: Dict[str, List[str]] = {
    "Tract & Title Ownership": [
        "tract", "legal_description", "ogl_number", "owner_name",
        "owner_type", "owner_address", "gross_acres", "net_mineral_acres",
        "mineral_interest", "royalty_rate", "lease_status", "lessee",
        "source", "confidence", "remarks",
    ],
    "Leasehold WI Ownership": [
        "ogl_number", "tract", "legal_description", "wi_owner",
        "working_interest", "net_revenue_interest", "net_acres",
        "assignment_chain", "effective_date", "lease_status",
        "source", "remarks",
    ],
    "OGL Register": [
        "ogl_number", "lessor", "lessee", "instrument_date",
        "recorded_date", "book", "page", "legal_description",
        "gross_acres", "royalty_rate", "primary_term", "status",
        "source", "remarks",
    ],
    "Runsheet": [
        "entry_no", "instrument_date", "recorded_date", "doc_type",
        "grantor", "grantee", "instrument_number", "book", "page",
        "legal_description", "ogl_number", "notes", "source",
    ],
    "Wells": [
        "api_number", "well_name", "operator", "well_status",
        "spud_date", "completion_date", "formation", "section",
        "township", "range", "county", "source", "remarks",
    ],
    "Legal Crosswalk": [
        "runsheet_legal", "ogl_legal", "ogl_number", "match_score",
        "matched", "method", "remarks",
    ],
    "QA Checks": [
        "check", "severity", "result", "detail",
    ],
    "Spend Log": [
        "timestamp", "item", "image_id", "cost_usd", "running_total_usd",
        "cap_remaining_usd", "source", "note",
    ],
    "Sources": [
        "name", "source", "kind", "score", "chosen_base",
        "sheet_names", "total_rows", "path", "reasons",
    ],
    "Change Log": [
        "timestamp", "step", "action", "detail",
    ],
}

# Sheets that hold the actual ownership product (used by QA emptiness checks).
PRODUCT_SHEETS = [
    "Tract & Title Ownership",
    "Leasehold WI Ownership",
    "OGL Register",
]


def empty_frame(sheet: str):
    """Return an empty pandas DataFrame with this sheet's columns."""
    import pandas as pd

    return pd.DataFrame(columns=SHEETS[sheet])
