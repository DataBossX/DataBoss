"""Collect well/production data for the subject section.

Primary path: read any well data that already exists in the uploaded
workbooks (a "Well Data" sheet, or wells referenced on other sheets). Optional
path: query a public well-data source over the network -- but only when both a
network connection and an explicit source URL/key are configured, and the
result is always tagged with its source.

This module NEVER fabricates an API number, operator, or production date. When
nothing is found it returns a single explicit "Not Found" placeholder row so
the downstream HBP analysis stays honest.
"""
from __future__ import annotations

from typing import Dict, List

from .utils import LOG, NOT_FOUND, UNKNOWN


def collect_well_data(existing: Dict[str, Dict[str, dict]],
                      section: str, township: str, range_: str,
                      enable_download: bool = False) -> List[dict]:
    rows: List[dict] = []

    # 1) Harvest from any existing "well" sheets in uploaded workbooks.
    for src_name, sheets in existing.items():
        for sheet_name, payload in sheets.items():
            if "well" not in sheet_name.lower():
                continue
            headers = payload["headers"]
            for r in payload["rows"]:
                row = _map_well_row(headers, r, src_name, sheet_name)
                if row:
                    rows.append(row)

    # 2) Optional network lookup (gated).
    if enable_download:
        try:
            net_rows = _download_well_data(section, township, range_)
            rows.extend(net_rows)
        except Exception as exc:  # pragma: no cover - network dependent
            LOG.warning("Well-data download skipped/failed: %s", exc)

    if not rows:
        rows.append({
            "Well Name": NOT_FOUND,
            "API": NOT_FOUND,
            "Operator": NOT_FOUND,
            "Location": NOT_FOUND,
            "Section-Township-Range": f"{section}-{township}-{range_}",
            "Formation": UNKNOWN,
            "Status": NOT_FOUND,
            "Spud Date": NOT_FOUND,
            "Completion Date": NOT_FOUND,
            "First Production": NOT_FOUND,
            "Last Production Found": NOT_FOUND,
            "Lease/Unit": UNKNOWN,
            "HBP Relevance": "No well data available; HBP cannot be confirmed",
            "Source": "No source available in this environment",
            "Notes": "No local well data and no network source configured/reachable",
            "Confidence": 0,
        })
    LOG.info("Collected %d well-data row(s)", len(rows))
    return rows


def _map_well_row(headers, row, src, sheet) -> dict | None:
    def g(*keys):
        for i, h in enumerate(headers):
            hl = (h or "").lower()
            if any(k in hl for k in keys) and i < len(row) and row[i] not in (None, ""):
                return str(row[i])
        return ""

    name = g("well name", "well", "name")
    api = g("api")
    if not name and not api:
        return None
    return {
        "Well Name": name or UNKNOWN,
        "API": api or UNKNOWN,
        "Operator": g("operator") or UNKNOWN,
        "Location": g("location", "lat", "long") or UNKNOWN,
        "Section-Township-Range": g("section", "str", "legal") or UNKNOWN,
        "Formation": g("formation", "reservoir") or UNKNOWN,
        "Status": g("status") or UNKNOWN,
        "Spud Date": g("spud") or UNKNOWN,
        "Completion Date": g("completion", "comp date") or UNKNOWN,
        "First Production": g("first prod") or UNKNOWN,
        "Last Production Found": g("last prod") or UNKNOWN,
        "Lease/Unit": g("lease", "unit") or UNKNOWN,
        "HBP Relevance": g("hbp") or "Verify against lease terms",
        "Source": f"{src}:{sheet}",
        "Notes": "Carried from uploaded workbook",
        "Confidence": 60,
    }


def _download_well_data(section, township, range_) -> List[dict]:
    """Placeholder for a real well-data API integration.

    Intentionally returns nothing unless a concrete, authorized source is wired
    in via configuration. Kept side-effect free to honor the truth rule.
    """
    LOG.info("Network well-data lookup requested for %s-%s-%s but no concrete "
             "authorized source is wired in; returning no rows.",
             section, township, range_)
    return []
