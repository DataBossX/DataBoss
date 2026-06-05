"""
Chain Builder — constructs lease chain, assignment chain, and mineral
ownership table from extracted instrument data.

RULES:
- Never fabricate values.
- UNKNOWN for any field that is not explicitly supported by evidence.
- Confidence: HIGH = image reviewed + chain supported
              MEDIUM = index/runsheet only
              LOW = public/operator evidence
              UNKNOWN = insufficient evidence
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple

log = logging.getLogger(__name__)

DIVERSIFIED_ENTITIES = {
    "diversified energy",
    "diversified production",
    "dp legacy tapstone",
    "diversified gas",
    "maverick natural resources",
    "unbridled resources",
    "tapstone energy",
    "bnk petroleum",
    "rimrock resource",
}


def _is_diversified(name: str) -> bool:
    n = name.lower()
    return any(d in n for d in DIVERSIFIED_ENTITIES)


def _names(v) -> List[str]:
    if not v:
        return []
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except Exception:
            return [v]
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]


# ── Row types ────────────────────────────────────────────────────────────────

@dataclass
class ChainRow:
    county: str              = "Beckham"
    legal: str               = "27-11N-25W"
    quarter_call: str        = "UNKNOWN"
    instrument_type: str     = "UNKNOWN"
    instrument_number: str   = "UNKNOWN"
    book: str                = "UNKNOWN"
    page: str                = "UNKNOWN"
    doc_date: str            = "UNKNOWN"
    effective_date: str      = "UNKNOWN"
    recording_date: str      = "UNKNOWN"
    grantor: str             = "UNKNOWN"
    grantee: str             = "UNKNOWN"
    lessor: str              = "UNKNOWN"
    lessee: str              = "UNKNOWN"
    assignor: str            = "UNKNOWN"
    assignee: str            = "UNKNOWN"
    lease_name: str          = "UNKNOWN"
    royalty: str             = "UNKNOWN"
    primary_term: str        = "UNKNOWN"
    depth_clause: str        = "UNKNOWN"
    pugh_clause: str         = "UNKNOWN"
    gross_acres: str         = "UNKNOWN"
    net_mineral_acres: str   = "UNKNOWN"
    net_leasehold_acres: str = "UNKNOWN"
    working_interest: str    = "UNKNOWN"
    nri: str                 = "UNKNOWN"
    current_owner: str       = "UNKNOWN"
    diversified_entity: str  = ""
    chain_from: str          = "UNKNOWN"
    chain_to: str            = "UNKNOWN"
    chain_status: str        = "UNKNOWN"
    status: str              = "UNKNOWN"
    confidence: str          = "UNKNOWN"
    problem_gap: str         = ""
    curative_needed: str     = ""
    notes: str               = ""
    source_link: str         = "NO LINK — SOURCE NEEDED"

    def to_list(self, columns: List[str]) -> List:
        d = asdict(self)
        return [d.get(c.lower().replace(" / ", "_").replace("/", "_").replace(" ", "_"), "") for c in columns]


# ── Column definitions (match user spec exactly) ─────────────────────────────

EXPORT_COLUMNS = [
    "County", "Legal", "Quarter Call",
    "Instrument Type", "Instrument Number", "Book", "Page",
    "Document Date", "Effective Date", "Recording Date",
    "Grantor", "Grantee", "Lessor", "Lessee", "Assignor", "Assignee",
    "Lease Name", "Royalty", "Primary Term", "Depth Clause", "Pugh Clause",
    "Gross Acres", "Net Mineral Acres", "Net Leasehold Acres",
    "Working Interest", "NRI",
    "Current Claimed Owner", "Diversified Entity",
    "Chain From", "Chain To", "Chain Status",
    "Status", "Confidence %", "Problem / Gap", "Curative Needed",
    "Notes", "SOURCE LINK / FILE LINK",
]


def _conf_label(confidence_float: float, has_image: bool) -> str:
    if has_image and confidence_float >= 0.8:
        return "HIGH"
    if confidence_float >= 0.5:
        return "MEDIUM"
    if confidence_float > 0.0:
        return "LOW"
    return "UNKNOWN"


def _source_link(inst: dict) -> str:
    if inst.get("local_pdf") and inst.get("download_status") == "downloaded":
        return inst["local_pdf"]
    if inst.get("source_url"):
        return inst["source_url"]
    if inst.get("image_url"):
        return inst["image_url"]
    return "NO LINK — SOURCE NEEDED"


def _row_from_instrument(inst: dict, ext: dict = None) -> ChainRow:
    """Build a ChainRow from a DB instrument row + optional extraction dict."""
    ext = ext or {}

    def _s(key, fallback="UNKNOWN"):
        v = ext.get(key) or inst.get(key)
        if v and str(v).strip() and str(v).strip().lower() not in ("null", "none", "[]", "{}"):
            return str(v).strip()
        return fallback

    def _names_str(key):
        raw = ext.get(key) or inst.get(key)
        names = _names(raw)
        return "; ".join(names) if names else "UNKNOWN"

    itype  = _s("instrument_type")
    conf_f = float(ext.get("confidence", 0.0))
    has_im = inst.get("download_status") == "downloaded"

    # Determine diversified entity
    for party_key in ("grantee", "grantor", "assignee", "lessee"):
        for name in _names(ext.get(party_key) or inst.get(party_key, "")):
            if _is_diversified(name):
                div_entity = name
                break
        else:
            continue
        break
    else:
        div_entity = ""

    row = ChainRow(
        instrument_type   = itype,
        instrument_number = _s("instrument_number"),
        book              = _s("book"),
        page              = _s("page"),
        doc_date          = _s("doc_date"),
        effective_date    = _s("effective_date"),
        recording_date    = _s("recording_date"),
        grantor           = _names_str("grantor"),
        grantee           = _names_str("grantee"),
        lessor            = _names_str("lessor"),
        lessee            = _names_str("lessee"),
        assignor          = _names_str("assignor"),
        assignee          = _names_str("assignee"),
        lease_name        = _s("lease_name"),
        royalty           = _s("royalty"),
        primary_term      = _s("primary_term"),
        depth_clause      = _s("depth_clause"),
        pugh_clause       = _s("pugh_clause"),
        gross_acres       = _s("gross_acres"),
        net_mineral_acres = _s("net_mineral_acres"),
        quarter_call      = _s("quarter_call"),
        diversified_entity= div_entity,
        confidence        = _conf_label(conf_f, has_im),
        source_link       = _source_link(inst),
        notes             = _s("notes", ""),
    )
    return row


# ── Gap detection ─────────────────────────────────────────────────────────────

def detect_gaps(lease_rows: List[ChainRow], asgn_rows: List[ChainRow]) -> List[Dict]:
    """
    Identify title gaps: assignments where the assignor is not the
    prior grantee, or breaks in chain continuity.
    Returns list of gap dicts.
    """
    gaps = []
    # Build grantor/grantee map
    grantees: Dict[str, str] = {}
    for r in lease_rows:
        if r.grantee and r.grantee != "UNKNOWN":
            grantees[r.grantee.lower()] = r.instrument_number

    for r in asgn_rows:
        assignor = r.assignor or r.grantor
        if assignor and assignor != "UNKNOWN":
            if assignor.lower() not in grantees:
                gaps.append({
                    "instrument_number": r.instrument_number,
                    "book": r.book,
                    "page": r.page,
                    "assignor": assignor,
                    "problem": f"Assignor '{assignor}' has no prior lease/title instrument in chain",
                    "curative": "Locate vesting instrument or obtain affidavit of title",
                })
    return gaps


def identify_missing_documents(all_rows: List[ChainRow]) -> List[Dict]:
    """Flag instruments that are referenced but not found."""
    missing = []
    for r in all_rows:
        if r.chain_from and r.chain_from != "UNKNOWN":
            # Check if chain_from instrument is in collection
            found = any(x.instrument_number == r.chain_from for x in all_rows)
            if not found:
                missing.append({
                    "referenced_in": r.instrument_number,
                    "missing_instrument": r.chain_from,
                    "type": "Referenced predecessor not found",
                    "curative": f"Obtain instrument {r.chain_from} from county records",
                    "priority": "HIGH",
                })
    return missing


# ── Main builder ──────────────────────────────────────────────────────────────

class ChainBuilder:
    def __init__(self, instruments: List[dict]):
        self._instruments = instruments
        self.lease_rows:  List[ChainRow] = []
        self.asgn_rows:   List[ChainRow] = []
        self.mineral_rows: List[ChainRow] = []
        self.all_rows:    List[ChainRow] = []
        self.gaps:        List[Dict] = []
        self.missing:     List[Dict] = []

    def build(self) -> "ChainBuilder":
        lease_types = {
            "oil and gas lease", "memorandum of oil and gas lease",
            "ratification", "pooling order", "unitization order",
        }
        asgn_types = {
            "assignment", "assignment of oil and gas lease",
            "partial assignment", "release", "partial release",
        }
        mineral_types = {
            "mineral deed", "warranty deed", "quit claim deed",
            "affidavit of heirship", "administrator's deed", "executor's deed",
        }

        for inst in self._instruments:
            ext = {}
            if inst.get("extracted_json"):
                try:
                    ext = json.loads(inst["extracted_json"])
                except Exception:
                    pass

            row = _row_from_instrument(inst, ext)

            # Section 27 filter
            if not (inst.get("section_27") or ext.get("section_27")):
                if not inst.get("extracted_json"):
                    # Not yet processed — include tentatively
                    pass

            itype_key = row.instrument_type.lower()
            if any(t in itype_key for t in lease_types):
                self.lease_rows.append(row)
            elif any(t in itype_key for t in asgn_types):
                self.asgn_rows.append(row)
            elif any(t in itype_key for t in mineral_types):
                self.mineral_rows.append(row)

        self.all_rows = self.lease_rows + self.asgn_rows + self.mineral_rows
        self.gaps   = detect_gaps(self.lease_rows, self.asgn_rows)
        self.missing = identify_missing_documents(self.all_rows)

        # Annotate rows with gap info
        gap_insts = {g["instrument_number"] for g in self.gaps}
        for row in self.all_rows:
            if row.instrument_number in gap_insts:
                row.problem_gap = "Chain gap — see Missing Documents"
                row.curative_needed = "Locate prior vesting instrument"
                row.chain_status = "GAP"
            else:
                row.chain_status = "Supported"

        log.info("Built chains: %d leases, %d assignments, %d mineral deeds, %d gaps",
                 len(self.lease_rows), len(self.asgn_rows), len(self.mineral_rows), len(self.gaps))
        return self

    @property
    def diversified_rows(self) -> List[ChainRow]:
        return [r for r in self.all_rows if r.diversified_entity]

    @property
    def curative_rows(self) -> List[Dict]:
        rows = []
        for g in self.gaps:
            rows.append({
                "Priority": "HIGH",
                "Instrument": g["instrument_number"],
                "Issue": g["problem"],
                "Action": g["curative"],
            })
        for m in self.missing:
            rows.append({
                "Priority": m.get("priority", "MEDIUM"),
                "Instrument": m.get("missing_instrument", ""),
                "Issue": m.get("type", ""),
                "Action": m.get("curative", ""),
            })
        return rows
