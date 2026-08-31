#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deep Conveyance, Reservation, Depth, and Royalty Parser (DataBossX / Horizon)
============================================================================

Extracts human-style legal title conveyance details, reservations, depth
severances, royalties, working interests, and net mineral acreages from deed
clauses, assignment language, lease terms, and probate decrees.

Supports:
1. ARTI (All Right, Title, and Interest) conveyance detection and resolution
2. Fractional & Proportionate conveyances ("undivided 1/2", "1/2 of Grantor's interest")
3. Depth Severances & Stratigraphic intervals ("surface to base of Morrow", "below 10,000'")
4. Mineral / Executive / Royalty Reservations ("reserving an undivided 1/4 mineral interest")
5. Lease Royalties (1/8, 3/16, 1/5, 1/4), ORRI, WI, and NRI calculations
6. Human-readable Title Examiner remarks generation
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from typing import Any, Dict, List, Optional, Tuple

from .interest import FULL, format_fraction, parse_acres, parse_interest, try_parse_interest

# Regex patterns for conveyance types
_ARTI_PATTERN = re.compile(
    r"\b(all\s+(?:of\s+)?(?:our\s+|my\s+|grantor['’]?s\s+)?(?:right[,\s]+title[,\s]+(?:and\s+)?interest|interest|r\.?t\.?i\.?|arti))\b",
    re.IGNORECASE,
)

_UNDIVIDED_FRACTION_PATTERN = re.compile(
    r"\b(?:an?\s+)?undivided\s+(\d+/\d+|\d+\.\d+|\d+)\s*(?:part|interest|mineral\s+interest|royalty)?\b",
    re.IGNORECASE,
)

_FRACTION_OF_GRANTOR_PATTERN = re.compile(
    r"\b(\d+/\d+|\d+\.\d+|\d+|half|one-half|one-fourth|one-third|all)\s+(?:of\s+)?(?:grantor['’]?s|our|my|their|his|her)\s+(?:remaining\s+)?(?:right[,\s]+title[,\s]+and\s+)?interest\b",
    re.IGNORECASE,
)

_RESERVATION_PATTERN = re.compile(
    r"\b(reserv(?:ing|es|ed)?|except(?:ing|ed|s)?|subject\s+to\s+a\s+reservation\s+of)\s+(?:unto\s+grantor[,\s]+)?([^.;\n]+)",
    re.IGNORECASE,
)

_DEPTH_PATTERN = re.compile(
    r"\b(?:depths?|formation|interval|strata|stratigraphic|depth\s+severance)\s*(?:from|between|limited\s+to|below|above|down\s+to|from\s+the\s+surface\s+to)\s*([^.;\n]+)",
    re.IGNORECASE,
)

_ROYALTY_PATTERN = re.compile(
    r"(?:\b(?:royalty|royalty\s+rate|reserved\s+royalty|lease\s+royalty)\s*(?:of\s+|is\s+|equal\s+to\s+)?(\d+/\d+|\d+\.\d+%\s*|\d+%\s*|\d+\.\d+)\b|\b(\d+/\d+|\d+\.\d+%\s*|\d+%\s*|\d+\.\d+)(?:th|st|nd|rd)?\s*(?:part|share)?\s*(?:royalty|royalty\s+rate)\b)",
    re.IGNORECASE,
)

_ORRI_PATTERN = re.compile(
    r"\b(?:orri|overriding\s+royalty(?:\s+interest)?)\s*(?:of\s+)?(\d+/\d+|\d+\.\d+%\s*|\d+%\s*|\d+\.\d+)\s*(?:of\s+8/8ths?|of\s+8/8)?\b",
    re.IGNORECASE,
)

_WI_PATTERN = re.compile(
    r"\b(?:wi|working\s+interest)\s*(?:of\s+)?(\d+/\d+|\d+\.\d+%\s*|\d+%\s*|\d+\.\d+)\b",
    re.IGNORECASE,
)


@dataclass
class ConveyanceDetails:
    raw_clause: str = ""
    conveyance_type: str = "Conveyance"  # ARTI, Undivided Fraction, Proportionate Grantor, Mineral Deed, Lease, etc.
    is_arti: bool = False
    is_undivided: bool = False
    is_fraction_of_grantor: bool = False
    fraction_stated: Optional[str] = None
    parsed_fraction: Optional[Fraction] = None
    conveyed_interest_display: str = ""
    retained_interest_display: str = ""
    reservation_clause: str = ""
    has_reservation: bool = False
    depth_clause: str = "All Depths"
    is_depth_severed: bool = False
    royalty_stated: Optional[str] = None
    royalty_fraction: Optional[Fraction] = None
    orri_stated: Optional[str] = None
    orri_fraction: Optional[Fraction] = None
    wi_stated: Optional[str] = None
    wi_fraction: Optional[Fraction] = None
    nri_stated: Optional[str] = None
    nri_fraction: Optional[Fraction] = None
    human_summary: str = ""
    assumptions: List[str] = field(default_factory=list)
    curative_notes: List[str] = field(default_factory=list)


def parse_fraction_word(word: str) -> Optional[Fraction]:
    low = word.lower().strip()
    if low in ("half", "one-half", "1/2", "0.5", "50%"):
        return Fraction(1, 2)
    if low in ("one-fourth", "one-quarter", "1/4", "0.25", "25%"):
        return Fraction(1, 4)
    if low in ("one-third", "1/3"):
        return Fraction(1, 3)
    if low in ("three-fourths", "three-quarters", "3/4", "0.75", "75%"):
        return Fraction(3, 4)
    if low in ("one-eighth", "1/8", "0.125", "12.5%"):
        return Fraction(1, 8)
    if low in ("three-sixteenths", "3/16", "0.1875", "18.75%"):
        return Fraction(3, 16)
    if low in ("one-fifth", "1/5", "0.2", "20%"):
        return Fraction(1, 5)
    if low in ("all", "entire", "100%", "1", "1/1", "8/8"):
        return Fraction(1, 1)
    return try_parse_interest(word)


def parse_conveyance_text(
    text: str,
    grantor_prior_interest: Optional[Fraction] = None,
    gross_tract_acres: Optional[Fraction] = None,
    doc_type: Optional[str] = None,
) -> ConveyanceDetails:
    """Parse raw text/remarks/clauses into a structured ConveyanceDetails object."""
    details = ConveyanceDetails(raw_clause=text)
    if not text or not text.strip():
        details.human_summary = "No conveyance details provided."
        return details

    clean_text = text.strip()

    # 1. Check ARTI
    arti_match = _ARTI_PATTERN.search(clean_text)
    if arti_match:
        details.is_arti = True
        details.conveyance_type = "All Right, Title, and Interest (ARTI)"

    # 2. Check Fraction of Grantor's Interest
    grantor_frac_match = _FRACTION_OF_GRANTOR_PATTERN.search(clean_text)
    if grantor_frac_match:
        details.is_fraction_of_grantor = True
        frac_str = grantor_frac_match.group(1)
        details.fraction_stated = frac_str
        f = parse_fraction_word(frac_str)
        if f is not None:
            details.parsed_fraction = f
            details.conveyance_type = f"Proportionate ({frac_str} of Grantor's Interest)"

    # 3. Check Undivided Fraction
    if not details.parsed_fraction:
        undiv_match = _UNDIVIDED_FRACTION_PATTERN.search(clean_text)
        if undiv_match:
            details.is_undivided = True
            frac_str = undiv_match.group(1)
            details.fraction_stated = frac_str
            f = parse_fraction_word(frac_str)
            if f is not None:
                details.parsed_fraction = f
                details.conveyance_type = f"Undivided {format_fraction(f)} Interest"

    # 4. Check bare fraction in text if not found yet
    if not details.parsed_fraction and not details.is_arti:
        # Search for standard fraction patterns like 1/2, 1/4, 1/16, 5/128, etc.
        frac_m = re.search(r"\b(\d+/\d+)\b", clean_text)
        if frac_m:
            frac_str = frac_m.group(1)
            f = try_parse_interest(frac_str)
            if f is not None:
                details.parsed_fraction = f
                details.fraction_stated = frac_str
                details.conveyance_type = f"Undivided {format_fraction(f)} Interest"

    # 5. Check Reservations
    res_match = _RESERVATION_PATTERN.search(clean_text)
    if res_match:
        details.has_reservation = True
        details.reservation_clause = res_match.group(0).strip()
    elif "reserving" in clean_text.lower() or "reservation" in clean_text.lower():
        details.has_reservation = True
        details.reservation_clause = "Reservation noted in instrument text"

    # 6. Check Depth Severances
    depth_match = _DEPTH_PATTERN.search(clean_text)
    if depth_match:
        details.is_depth_severed = True
        details.depth_clause = depth_match.group(0).strip()
    elif "formation" in clean_text.lower() or "below" in clean_text.lower() or "depth" in clean_text.lower():
        # Check specific formations
        for fmt in ["woodford", "morrow", "cherokee", "chester", "huntoon", "springer", "red fork", "tonkawa"]:
            if fmt in clean_text.lower():
                details.is_depth_severed = True
                details.depth_clause = f"Limited to / Severed at {fmt.title()} Formation"
                break

    # 7. Check Royalty / ORRI / WI
    roy_match = _ROYALTY_PATTERN.search(clean_text)
    if roy_match:
        details.royalty_stated = (roy_match.group(1) or roy_match.group(2) or "").strip()
        details.royalty_fraction = try_parse_interest(details.royalty_stated)

    orri_match = _ORRI_PATTERN.search(clean_text)
    if orri_match:
        details.orri_stated = orri_match.group(1)
        details.orri_fraction = try_parse_interest(details.orri_stated)

    wi_match = _WI_PATTERN.search(clean_text)
    if wi_match:
        details.wi_stated = wi_match.group(1)
        details.wi_fraction = try_parse_interest(details.wi_stated)

    # 8. Compute Conveyed Interest & Retained Interest strings
    # If ARTI:
    if details.is_arti:
        if grantor_prior_interest is not None:
            details.parsed_fraction = grantor_prior_interest
            details.conveyed_interest_display = f"ARTI ({format_fraction(grantor_prior_interest)} = 100% of Grantor)"
            details.retained_interest_display = "0.000000 (0/1)"
        else:
            details.conveyed_interest_display = "All Right, Title, and Interest (ARTI)"
            details.retained_interest_display = "0.000000 (Assumed all conveyed)"
            details.assumptions.append("Grantor assumed to convey 100% of their existing interest under ARTI clause.")

    # If Proportionate of Grantor:
    elif details.is_fraction_of_grantor and details.parsed_fraction is not None:
        if grantor_prior_interest is not None:
            conveyed = details.parsed_fraction * grantor_prior_interest
            retained = grantor_prior_interest - conveyed
            details.conveyed_interest_display = f"{format_fraction(details.parsed_fraction)} of Grantor ({format_fraction(conveyed)})"
            details.retained_interest_display = f"{format_fraction(retained)}"
        else:
            details.conveyed_interest_display = f"{format_fraction(details.parsed_fraction)} of Grantor's Interest"
            details.retained_interest_display = f"Remaining {(1 - details.parsed_fraction)} of Grantor's Interest"

    # If Undivided Fraction:
    elif details.parsed_fraction is not None:
        details.conveyed_interest_display = f"Undivided {format_fraction(details.parsed_fraction)} Interest"
        if grantor_prior_interest is not None:
            retained = grantor_prior_interest - details.parsed_fraction
            if retained >= 0:
                details.retained_interest_display = format_fraction(retained)
            else:
                details.retained_interest_display = f"OVER-CONVEYANCE by {format_fraction(abs(retained))}"
                details.curative_notes.append("Potential over-conveyance: conveyed interest exceeds grantor's prior record interest.")
        else:
            details.retained_interest_display = "TBD (Prior Grantor Interest Unspecified)"

    # Document Type Specific Handling
    doc_up = (doc_type or "").upper()
    if "PATENT" in doc_up or "FEDERAL PATENT" in doc_up:
        details.conveyance_type = "Patent (Mineral Fee)"
        details.parsed_fraction = FULL
        details.conveyed_interest_display = "100% Fee Simple (All Minerals)"
        details.retained_interest_display = "0.000000 (Sovereignty to Patentee)"
    elif "PROBATE" in doc_up or "FINAL DECREE" in doc_up or "DECREE" in doc_up:
        details.conveyance_type = "Probate / Final Decree"
        if details.parsed_fraction is None:
            details.conveyed_interest_display = "100% of Decedent's Estate Distributed"
            details.retained_interest_display = "0.000000 (Estate Closed)"
            details.assumptions.append("Final decree assumed to distribute entire remaining interest of decedent to named heirs.")
    elif "LEASE" in doc_up or "OGL" in doc_up:
        details.conveyance_type = "Oil & Gas Lease"
        if not details.conveyed_interest_display:
            details.conveyed_interest_display = "Leasehold Estate (Working Interest)"
        if details.royalty_stated:
            details.retained_interest_display = f"Lessor Royalty: {details.royalty_stated}"
        else:
            details.retained_interest_display = "Lessor Royalty (Standard 1/8 to 3/16)"

    # Build human summary narrative
    narrative_parts = []
    if details.conveyed_interest_display:
        narrative_parts.append(f"Conveys {details.conveyed_interest_display}")
    if details.has_reservation:
        narrative_parts.append(f"[{details.reservation_clause}]")
    if details.is_depth_severed:
        narrative_parts.append(f"[{details.depth_clause}]")
    if details.royalty_stated:
        narrative_parts.append(f"[Royalty: {details.royalty_stated}]")
    if details.orri_stated:
        narrative_parts.append(f"[ORRI: {details.orri_stated}]")

    details.human_summary = "; ".join(narrative_parts) if narrative_parts else clean_text

    return details


def calculate_net_mineral_acres(
    conveyed_fraction: Optional[Fraction],
    gross_tract_acres: Optional[Fraction],
) -> Optional[Fraction]:
    """Calculate exact Net Mineral Acres as Fraction."""
    if conveyed_fraction is None or gross_tract_acres is None:
        return None
    return conveyed_fraction * gross_tract_acres


def format_nma_display(nma_fraction: Optional[Fraction], precision: int = 6) -> str:
    """Format Net Mineral Acres as exact fraction and decimal string."""
    if nma_fraction is None:
        return "TBD"
    dec_val = float(nma_fraction)
    return f"{dec_val:.{precision}f} NMA ({format_fraction(nma_fraction)})"
