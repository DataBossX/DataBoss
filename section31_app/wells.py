"""Pull well data and add/update the Wells sheet.

Merges wells found in candidate workbooks with any wells returned by an external
source (OKCountyRecords / OCC client, injected). Wells are keyed by API number
(falling back to well name) so re-runs update in place rather than duplicating.
Only wells that plausibly touch Section 31-12N-24W are kept.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .config import RANGE, SECTION, TOWNSHIP
from .schema import SHEETS

_SEC_RE = re.compile(r"\b0?31\b")
_TWP_RE = re.compile(r"\b12\s*n\b", re.I)
_RNG_RE = re.compile(r"\b24\s*w\b", re.I)


def _touches_section(row: Dict) -> bool:
    sec = str(row.get("section", ""))
    twp = str(row.get("township", ""))
    rng = str(row.get("range", ""))
    blob = " ".join([sec, twp, rng, str(row.get("well_name", "")),
                     str(row.get("remarks", ""))])
    sec_ok = bool(_SEC_RE.search(sec)) or ("31" in blob and _SEC_RE.search(blob))
    # If no location fields at all, keep it (operator can prune) but tag it.
    if not any([sec, twp, rng]):
        return True
    return bool(sec_ok or (_TWP_RE.search(blob) and _RNG_RE.search(blob)))


def _key(row: Dict) -> str:
    api = re.sub(r"[^0-9]", "", str(row.get("api_number", "")))
    if api:
        return f"api:{api}"
    return "name:" + re.sub(r"[^a-z0-9]", "", str(row.get("well_name", "")).lower())


def build_wells(
    workbook_wells: List[Dict],
    external_wells: Optional[List[Dict]] = None,
) -> List[Dict]:
    cols = SHEETS["Wells"]
    index: Dict[str, Dict] = {}
    ordered: List[Dict] = []

    def add(raw: Dict, source_default: str):
        rec = {c: raw.get(c, "") for c in cols}
        # default the section identity when the source omitted it
        rec["section"] = rec.get("section") or SECTION
        rec["township"] = rec.get("township") or TOWNSHIP
        rec["range"] = rec.get("range") or RANGE
        rec["county"] = rec.get("county") or "Roger Mills"
        if not rec.get("source"):
            rec["source"] = source_default
        if not _touches_section(rec):
            return
        k = _key(rec)
        if not k.strip("apiname:"):
            return
        if k in index:
            existing = index[k]
            for col, val in rec.items():
                if val and not existing.get(col):
                    existing[col] = val
        else:
            index[k] = rec
            ordered.append(rec)

    for w in workbook_wells:
        add(w, "workbook")
    for w in (external_wells or []):
        add(w, "OCC/OKCountyRecords")
    return ordered
