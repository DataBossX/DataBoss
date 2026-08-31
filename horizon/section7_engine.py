#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Section 7 Title Examination & Current Ownership Rollup Engine (DataBossX / Horizon)
==================================================================================

Full-fidelity title chain engine, conveyance reconciler, gap detector, and
current ownership ledger builder tailored for Section 7 (and extensible to any
section / township / range).

Key features:
1. Exact Fraction-based title chain math (Grantor - Conveyed = Retained)
2. ARTI, Undivided Fractions, Depths, Reservations, and Royalty parsing
3. Automatic Gap Detection, Heuristic Assumption Generation, and Curative Flagging
4. Rollup of Current Mineral Owners with Net Acres, Addresses, Leases, and Royalties
5. Strict validation tying out ownership decimals to 1.0 (8/8ths) and gross acres
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .conveyance_parser import (
    ConveyanceDetails,
    calculate_net_mineral_acres,
    format_nma_display,
    parse_conveyance_text,
)
from .interest import FULL, format_fraction, parse_acres, parse_interest, try_parse_interest


@dataclass
class Section7Instrument:
    entry_no: int
    instrument_date: str
    recorded_date: str
    doc_type: str
    grantor: str
    grantee: str
    book: str = ""
    page: str = ""
    instrument_number: str = ""
    legal_description: str = "Sec 7-12N-24W: All (640.00 Gross Acres)"
    gross_acres: float = 640.0
    conveyance_text: str = ""
    grantor_address: str = ""
    grantee_address: str = ""
    depth_severance: str = "All Depths"
    reservation_text: str = ""
    royalty_rate: str = ""
    orri_rate: str = ""
    term_years: str = ""
    status: str = "ok"
    examiner_remarks: str = ""
    # Computed fields
    conveyance_details: Optional[ConveyanceDetails] = None
    calculated_conveyed_interest: str = ""
    calculated_retained_interest: str = ""
    calculated_net_acres: str = ""
    assumptions_made: List[str] = field(default_factory=list)
    curative_issues: List[str] = field(default_factory=list)


@dataclass
class CurrentOwnerRecord:
    owner_name: str
    owner_type: str  # Mineral Fee Owner, Royalty Owner, Working Interest, ORRI
    address: str
    fractional_interest: Fraction
    decimal_interest: float
    fraction_display: str
    net_mineral_acres: float
    lease_status: str  # Leased, Unleased, HBP, Federal Lease
    lease_reference: str
    royalty_rate: str
    net_revenue_interest: str
    remarks: str = ""


@dataclass
class Section7TitleReport:
    project_id: str = "DBX-OK-ROGER-MILLS-07-12N-24W"
    section: str = "7"
    township: str = "12N"
    range: str = "24W"
    county: str = "Roger Mills"
    state: str = "OK"
    gross_acres: float = 640.0
    effective_date: str = "2026-08-31"
    examiner_name: str = "DataBossX Horizon Automated Title Engine & Land Examiner"
    instruments: List[Section7Instrument] = field(default_factory=list)
    current_mineral_owners: List[CurrentOwnerRecord] = field(default_factory=list)
    current_leasehold_owners: List[CurrentOwnerRecord] = field(default_factory=list)
    curative_requirements: List[Dict[str, Any]] = field(default_factory=list)
    assumptions_ledger: List[Dict[str, Any]] = field(default_factory=list)
    total_ownership_decimal: float = 0.0
    total_net_mineral_acres: float = 0.0
    is_balanced: bool = False
    balance_difference_acres: float = 0.0


def extract_core_name(name: str) -> str:
    """Extract canonical core identity from complex legal entity and marital strings."""
    if not name:
        return "UNKNOWN"
    s = name.strip()
    s = re.sub(r"\s+", " ", s)

    # Strip estate prefix: "Estate of William H. Harrison, Deceased" -> "William H. Harrison"
    s = re.sub(r"^(?:the\s+)?estate\s+of\s+", "", s, flags=re.I)
    s = re.sub(r"^(?:the\s+)?trustees?\s+of\s+(?:the\s+)?", "", s, flags=re.I)
    s = re.sub(r"^(?:the\s+)?heirs?\s+of\s+", "", s, flags=re.I)

    # Strip trustee parentheses: "Harrison Family Mineral Trust (Robert Harrison, Trustee)" -> "Harrison Family Mineral Trust"
    s = re.sub(r"\s*\([^)]*trustee[^)]*\)", "", s, flags=re.I)
    s = re.sub(r"\s*\([^)]*\)", "", s)

    # Strip marital status & single person clauses
    s = re.sub(r",?\s+(?:husband\s+and\s+wife|a\s+single\s+person|his\s+wife|her\s+husband|a\s+married\s+man|a\s+married\s+woman|a\s+widow|a\s+widower|unmarried)$", "", s, flags=re.I)
    s = re.sub(r",?\s+(?:deceased|dec['’]?d)$", "", s, flags=re.I)
    s = re.sub(r",?\s+(?:individually\s+and\s+as\s+trustee|as\s+trustee|trustee|et\s+al\.?)$", "", s, flags=re.I)

    # Strip corporate endings for loose matching
    s = re.sub(r",?\s+(?:inc\.?|llc|corp\.?|corporation|company|co\.?|l\.?p\.?|ltd\.?)$", "", s, flags=re.I)

    return s.strip()


def normalize_party_name(name: str) -> str:
    """Normalize party name for stable chain linking."""
    return extract_core_name(name)


def resolve_grantor_in_ledger(
    grantor_raw: str,
    mineral_ledger: Dict[str, Fraction],
) -> Tuple[str, Fraction]:
    """Find matching grantor key in mineral ledger with non-zero interest balance."""
    clean_g = normalize_party_name(grantor_raw)

    # 1. Exact match
    if clean_g in mineral_ledger and mineral_ledger[clean_g] > 0:
        return clean_g, mineral_ledger[clean_g]

    # 2. Check if raw grantor contains " and " (e.g. "William H. Harrison and Sarah Harrison")
    if " and " in grantor_raw.lower():
        parts = re.split(r"\s+and\s+", grantor_raw, flags=re.I)
        for part in parts:
            p_clean = normalize_party_name(part)
            if p_clean in mineral_ledger and mineral_ledger[p_clean] > 0:
                return p_clean, mineral_ledger[p_clean]

    # 3. Fuzzy / Substring match against active holders in ledger
    for holder, bal in mineral_ledger.items():
        if bal > 0:
            h_clean = normalize_party_name(holder)
            if h_clean in clean_g or clean_g in h_clean:
                return holder, bal
            # Check individual tokens
            h_tokens = set(h_clean.lower().split())
            g_tokens = set(clean_g.lower().split())
            if len(h_tokens & g_tokens) >= 2:
                return holder, bal

    # Not found in ledger with positive balance
    return clean_g, mineral_ledger.get(clean_g, Fraction(0, 1))


def run_section7_title_chain(
    raw_instruments: Sequence[Dict[str, Any]],
    gross_tract_acres: float = 640.0,
    section_legal: str = "Section 7-12N-24W, Roger Mills County, OK (640.00 Gross Acres)",
) -> Section7TitleReport:
    """Execute complete title examination, conveyance parsing, exact chaining, and ownership rollup."""
    gross_frac = Fraction(Decimal(str(gross_tract_acres)))

    report = Section7TitleReport(
        gross_acres=gross_tract_acres,
        effective_date=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d"),
    )

    # Mineral Fee ledger: maps normalized owner name -> current Fraction held
    mineral_ledger: Dict[str, Fraction] = defaultdict(Fraction)
    owner_addresses: Dict[str, str] = {}
    owner_leases: Dict[str, Dict[str, str]] = {}

    processed_instruments: List[Section7Instrument] = []
    assumptions: List[Dict[str, Any]] = []
    curative: List[Dict[str, Any]] = []

    for idx, raw in enumerate(raw_instruments, 1):
        grantor_raw = str(raw.get("grantor") or "").strip()
        grantee_raw = str(raw.get("grantee") or "").strip()
        doc_type = str(raw.get("doc_type") or "Deed").strip()
        book = str(raw.get("book") or "").strip()
        page = str(raw.get("page") or "").strip()
        inst_no = str(raw.get("instrument_number") or f"{book}/{page}").strip()
        inst_date = str(raw.get("instrument_date") or "").strip()
        rec_date = str(raw.get("recorded_date") or "").strip()
        clause = str(raw.get("conveyance_text") or raw.get("remarks") or "").strip()
        grantor_addr = str(raw.get("grantor_address") or "").strip()
        grantee_addr = str(raw.get("grantee_address") or "").strip()
        stated_gross = float(raw.get("gross_acres") or gross_tract_acres)
        depth_sev = str(raw.get("depth_severance") or "All Depths").strip()
        res_text = str(raw.get("reservation_text") or "").strip()
        roy_rate = str(raw.get("royalty_rate") or "").strip()

        if grantee_addr:
            owner_addresses[grantee_raw] = grantee_addr
            owner_addresses[normalize_party_name(grantee_raw)] = grantee_addr
        if grantor_addr:
            if grantor_raw not in owner_addresses:
                owner_addresses[grantor_raw] = grantor_addr
            if normalize_party_name(grantor_raw) not in owner_addresses:
                owner_addresses[normalize_party_name(grantor_raw)] = grantor_addr

        # Look up grantor's current held interest using intelligent entity resolution
        grantor_key, grantor_prior = resolve_grantor_in_ledger(grantor_raw, mineral_ledger)

        # Parse conveyance details with deep extractor
        conv_details = parse_conveyance_text(
            text=clause,
            grantor_prior_interest=grantor_prior if grantor_prior > 0 else None,
            gross_tract_acres=gross_frac,
            doc_type=doc_type,
        )

        # Merge any manual overrides
        if res_text and not conv_details.has_reservation:
            conv_details.has_reservation = True
            conv_details.reservation_clause = res_text
        if depth_sev and depth_sev != "All Depths" and not conv_details.is_depth_severed:
            conv_details.is_depth_severed = True
            conv_details.depth_clause = depth_sev
        if roy_rate and not conv_details.royalty_stated:
            conv_details.royalty_stated = roy_rate
            conv_details.royalty_fraction = try_parse_interest(roy_rate)

        # Handle specific chain logic based on document type
        doc_up = doc_type.upper()
        inst_assumptions = list(conv_details.assumptions)
        inst_curative = list(conv_details.curative_notes)
        net_acres_conveyed_frac: Optional[Fraction] = None

        if "PATENT" in doc_up or idx == 1 and not grantor_raw:
            # Root sovereign patent
            mineral_ledger[normalize_party_name(grantee_raw)] = FULL
            conv_details.conveyed_interest_display = "100% Fee Simple (All Minerals)"
            conv_details.retained_interest_display = "0.000000 (Sovereignty to Patentee)"
            net_acres_conveyed_frac = gross_frac

        elif "LEASE" in doc_up or "OGL" in doc_up:
            # Leasehold conveyance -- does not reduce mineral fee, creates leasehold estate
            lease_ref = f"Book {book}/Page {page}" if book and page else inst_no
            owner_leases[grantor_key] = {
                "lease_ref": lease_ref,
                "lessee": grantee_raw,
                "royalty": conv_details.royalty_stated or "3/16 (18.75%)",
                "term": raw.get("term_years") or "3 Years",
                "status": "HBP / Active Lease",
            }
            conv_details.conveyed_interest_display = "Leasehold Estate (Working Interest)"
            conv_details.retained_interest_display = f"Lessor Royalty: {conv_details.royalty_stated or '3/16'}"

        elif "ASSIGNMENT" in doc_up and ("OVERRIDING" in doc_up or "ORRI" in doc_up):
            # ORRI assignment
            conv_details.conveyed_interest_display = f"ORRI of {conv_details.orri_stated or '2.0% of 8/8'}"
            conv_details.retained_interest_display = "WI reduced by ORRI burden"

        else:
            # Standard Mineral Deed / Warranty Deed / Probate Conveyance
            conveyed_frac = conv_details.parsed_fraction

            # Check if Grantor had interest in ledger
            if grantor_prior == Fraction(0, 1):
                # Chain Gap: Grantor conveyed without prior record interest in ledger
                assumed_frac = conveyed_frac if conveyed_frac is not None else Fraction(1, 1)
                inst_assumptions.append(
                    f"[ASSUMPTION]: Grantor '{grantor_raw}' assumed to hold at least {format_fraction(assumed_frac)} interest via unindexed/prior conveyance."
                )
                inst_curative.append(
                    f"Chain Gap at Entry {idx} (Book {book}/Page {page}): No prior deed of record into Grantor '{grantor_raw}'. Require recorded source deed into Grantor."
                )
                grantor_prior = assumed_frac

            if conveyed_frac is not None:
                if conv_details.is_fraction_of_grantor:
                    actual_conveyed = conveyed_frac * grantor_prior
                elif conv_details.is_arti:
                    actual_conveyed = grantor_prior
                else:
                    actual_conveyed = conveyed_frac

                # Check for over-conveyance
                if actual_conveyed > grantor_prior:
                    inst_curative.append(
                        f"Over-Conveyance at Entry {idx}: Conveyance of {format_fraction(actual_conveyed)} exceeds Grantor's held {format_fraction(grantor_prior)}."
                    )
                    actual_conveyed = grantor_prior  # Cap at available

                grantor_retained = grantor_prior - actual_conveyed
                mineral_ledger[grantor_key] = grantor_retained

                grantee_key = normalize_party_name(grantee_raw)
                mineral_ledger[grantee_key] = mineral_ledger.get(grantee_key, Fraction(0, 1)) + actual_conveyed

                net_acres_conveyed_frac = actual_conveyed * gross_frac
                conv_details.conveyed_interest_display = (
                    f"ARTI ({format_fraction(actual_conveyed)})"
                    if conv_details.is_arti
                    else f"Undivided {format_fraction(actual_conveyed)} Interest"
                )
                conv_details.retained_interest_display = format_fraction(grantor_retained)
            else:
                # No fraction parseable
                inst_assumptions.append(
                    f"[ASSUMPTION]: Undivided conveyance by '{grantor_raw}' assumed to convey all remaining interest."
                )
                actual_conveyed = grantor_prior
                mineral_ledger[grantor_key] = Fraction(0, 1)
                grantee_key = normalize_party_name(grantee_raw)
                mineral_ledger[grantee_key] = mineral_ledger.get(grantee_key, Fraction(0, 1)) + actual_conveyed
                conv_details.conveyed_interest_display = f"All Right, Title, and Interest ({format_fraction(actual_conveyed)})"
                conv_details.retained_interest_display = "0.000000"
                net_acres_conveyed_frac = actual_conveyed * gross_frac

        # Build clean examiner remarks
        remark_components = []
        if conv_details.human_summary:
            remark_components.append(conv_details.human_summary)
        for a in inst_assumptions:
            remark_components.append(a)
            assumptions.append({"entry_no": idx, "grantor": grantor_raw, "grantee": grantee_raw, "assumption": a})
        for c in inst_curative:
            remark_components.append(f"[CURATIVE]: {c}")
            curative.append({"entry_no": idx, "book_page": f"{book}/{page}", "issue": c})

        final_remarks = " | ".join(remark_components)

        inst_obj = Section7Instrument(
            entry_no=idx,
            instrument_date=inst_date,
            recorded_date=rec_date,
            doc_type=doc_type,
            grantor=grantor_raw,
            grantee=grantee_raw,
            book=book,
            page=page,
            instrument_number=inst_no,
            legal_description=raw.get("legal_description") or section_legal,
            gross_acres=stated_gross,
            conveyance_text=clause,
            grantor_address=grantor_addr,
            grantee_address=grantee_addr,
            depth_severance=conv_details.depth_clause,
            reservation_text=conv_details.reservation_clause,
            royalty_rate=conv_details.royalty_stated or "",
            orri_rate=conv_details.orri_stated or "",
            status="ok" if not inst_curative else "Needs Examiner Review",
            examiner_remarks=final_remarks,
            conveyance_details=conv_details,
            calculated_conveyed_interest=conv_details.conveyed_interest_display,
            calculated_retained_interest=conv_details.retained_interest_display,
            calculated_net_acres=format_nma_display(net_acres_conveyed_frac) if net_acres_conveyed_frac else "—",
            assumptions_made=inst_assumptions,
            curative_issues=inst_curative,
        )
        processed_instruments.append(inst_obj)

    report.instruments = processed_instruments
    report.assumptions_ledger = assumptions
    report.curative_requirements = curative

    # Build Current Mineral Owners Table
    current_owners: List[CurrentOwnerRecord] = []
    total_dec = 0.0
    total_nma = 0.0

    for name, frac in mineral_ledger.items():
        if frac > 0:
            dec_val = float(frac)
            nma_val = float(frac * gross_frac)
            total_dec += dec_val
            total_nma += nma_val

            # Lease lookup
            lease_info = owner_leases.get(name) or owner_leases.get(normalize_party_name(name))
            if not lease_info:
                for lk, lv in owner_leases.items():
                    if lk in name or name in lk:
                        lease_info = lv
                        break
            lease_info = lease_info or {}

            l_status = "Leased (HBP)" if lease_info else "Unleased / Open Mineral Fee"
            l_ref = lease_info.get("lease_ref", "None of Record")
            l_roy = lease_info.get("royalty", "Unleased (N/A)")
            l_nri = f"{(dec_val * (1.0 - 0.1875)):.6f}" if lease_info else "1.000000 (8/8)"

            addr = owner_addresses.get(name) or owner_addresses.get(normalize_party_name(name))
            if not addr:
                for ak, av in owner_addresses.items():
                    if ak in name or name in ak:
                        addr = av
                        break
            addr = addr or "Address Not Specified in Record"

            owner_rec = CurrentOwnerRecord(
                owner_name=name,
                owner_type="Current Mineral Fee Owner",
                address=addr,
                fractional_interest=frac,
                decimal_interest=dec_val,
                fraction_display=format_fraction(frac),
                net_mineral_acres=round(nma_val, 6),
                lease_status=l_status,
                lease_reference=l_ref,
                royalty_rate=l_roy,
                net_revenue_interest=l_nri,
                remarks=f"Current fee holder of undivided {format_fraction(frac)} interest in Section 7.",
            )
            current_owners.append(owner_rec)

    # Sort owners by largest net acres descending
    current_owners.sort(key=lambda x: x.net_mineral_acres, reverse=True)

    report.current_mineral_owners = current_owners
    report.total_ownership_decimal = round(total_dec, 6)
    report.total_net_mineral_acres = round(total_nma, 6)
    report.is_balanced = abs(total_dec - 1.0) < 0.0001
    report.balance_difference_acres = round(gross_tract_acres - total_nma, 6)

    return report
