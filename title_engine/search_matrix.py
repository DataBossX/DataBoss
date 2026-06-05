"""
Search matrix for Section 27-11N-25W, Beckham County, Oklahoma.
Defines every query to run plus dynamic chaining logic.
"""

from dataclasses import dataclass, field
from typing import List, Dict

COUNTY = "Beckham"

# ── Legal description queries ─────────────────────────────────────────────────

LEGAL_QUERIES: List[Dict] = [
    {"type": "legal", "q": "27-11N-25W"},
    {"type": "legal", "q": "S27 T11N R25W"},
    {"type": "legal", "q": "27 11N 25W"},
    {"type": "legal", "q": "Section 27 Township 11 North Range 25 West"},
    {"type": "legal", "q": "Sec 27 T11N R25W"},
    # Section + township structured params
    {"type": "legal", "q": None, "section": "27", "township": "11N", "range_": "25W"},
]

# ── Quarter-section queries ───────────────────────────────────────────────────

_QUARTERS = ["NE/4", "NW/4", "SE/4", "SW/4"]
_QQ = [
    "NE/4 NE/4", "NW/4 NE/4", "SE/4 NE/4", "SW/4 NE/4",
    "NE/4 NW/4", "NW/4 NW/4", "SE/4 NW/4", "SW/4 NW/4",
    "NE/4 SE/4", "NW/4 SE/4", "SE/4 SE/4", "SW/4 SE/4",
    "NE/4 SW/4", "NW/4 SW/4", "SE/4 SW/4", "SW/4 SW/4",
]

QUARTER_QUERIES: List[Dict] = []
for q in _QUARTERS:
    QUARTER_QUERIES.append({"type": "quarter", "q": f"{q} 27-11N-25W"})
for qq in _QQ:
    QUARTER_QUERIES.append({"type": "quarter_quarter", "q": f"{qq} 27-11N-25W"})

# ── Named entity queries ──────────────────────────────────────────────────────

PRIORITY_ENTITIES: List[str] = [
    "Diversified Energy",
    "Diversified Production LLC",
    "DP Legacy Tapstone LLC",
    "Diversified Gas & Oil",
    "Maverick Natural Resources",
    "Unbridled Resources LLC",
    "Tapstone Energy",
    "Tapstone Energy Holdings",
    "BNK Petroleum",
    "Rimrock Resource",
    "ConocoPhillips",
    "Oaktree",
    "Camino",
    "EIG",
]

ENTITY_QUERIES: List[Dict] = []
for e in PRIORITY_ENTITIES:
    ENTITY_QUERIES.append({"type": "entity_grantor",  "q": None, "grantor": e})
    ENTITY_QUERIES.append({"type": "entity_grantee",  "q": None, "grantee": e})

# ── Priority instrument types ────────────────────────────────────────────────

PRIORITY_TYPES = [
    "Oil and Gas Lease",
    "Memorandum of Oil and Gas Lease",
    "Assignment",
    "Assignment of Oil and Gas Leases",
    "Release",
    "Partial Release",
    "Ratification",
    "Correction",
    "Mineral Deed",
    "Warranty Deed",
    "Quit Claim Deed",
    "Affidavit of Heirship",
    "Pooling Order",
    "Unitization",
    "Mortgage",
    "UCC",
]

# ── All static queries ────────────────────────────────────────────────────────

ALL_STATIC_QUERIES: List[Dict] = (
    LEGAL_QUERIES
    + QUARTER_QUERIES
    + ENTITY_QUERIES
)


def build_dynamic_query(entity_name: str, entity_type: str) -> List[Dict]:
    """Build follow-up search queries for a newly discovered entity."""
    queries = []
    if entity_type in ("grantor", "assignor", "lessor"):
        queries.append({"type": "dynamic_grantor", "q": None, "grantor": entity_name})
    if entity_type in ("grantee", "assignee", "lessee"):
        queries.append({"type": "dynamic_grantee", "q": None, "grantee": entity_name})
    # Always search both sides for full chain
    queries.append({"type": "dynamic_grantor", "q": None, "grantor": entity_name})
    queries.append({"type": "dynamic_grantee", "q": None, "grantee": entity_name})
    # Deduplicate
    seen = set()
    unique = []
    for q in queries:
        key = str(q)
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique
