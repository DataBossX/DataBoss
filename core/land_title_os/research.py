"""County-record search-package generation (Move #51, with the name-variant
rules of Move #57).

For each unresolved party, generate the concrete searches a landman (or a
county-portal agent) should run: exact name, initial/spelling variants,
trust/trustee and entity-succession forms, constrained by instrument types,
date range, and section-township-range. Variants are search *leads* — the
identity rules in ``chain_graph`` still require evidence before merging.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ENTITY_SUFFIXES = ("llc", "l.l.c.", "inc", "inc.", "corp", "corp.", "corporation",
                   "company", "co.", "lp", "l.p.", "ltd", "partnership", "trust")

DEFAULT_INSTRUMENT_TYPES = [
    "deed", "mineral deed", "quitclaim deed", "oil and gas lease", "assignment",
    "probate", "affidavit", "mortgage", "release", "pooling order", "spacing order",
]


@dataclass
class SearchPackage:
    party: str
    section_township_range: str
    county: str
    state: str
    name_variants: list = field(default_factory=list)
    instrument_types: list = field(default_factory=list)
    date_range: str = "inception-present"
    notes: list = field(default_factory=list)


def _is_entity(name: str) -> bool:
    low = name.casefold()
    return any(low.rstrip(".").endswith(s.rstrip(".")) or f" {s} " in f"{low} "
               for s in ENTITY_SUFFIXES)


def name_variants(name: str) -> list[str]:
    """Deterministic variant list. Always includes the exact name first."""
    name = re.sub(r"\s+", " ", str(name)).strip()
    variants = [name]

    def add(v: str) -> None:
        v = re.sub(r"\s+", " ", v).strip(" ,")
        if v and v.casefold() not in {x.casefold() for x in variants}:
            variants.append(v)

    if _is_entity(name):
        # bare name without suffix, and common successor forms
        base = re.sub(r",?\s+(llc|l\.l\.c\.|inc\.?|corp\.?|corporation|company|co\.|"
                      r"lp|l\.p\.|ltd|partnership)$", "", name, flags=re.IGNORECASE)
        add(base)
        if "trust" not in name.casefold():
            add(f"{base} LLC")
            add(f"{base} Inc")
        return variants

    parts = name.split(" ")
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        middles = parts[1:-1]
        if middles:
            add(f"{first} {last}")                                  # drop middles
            initials = " ".join(f"{m[0]}." for m in middles if m)
            add(f"{first} {initials} {last}")                       # middle initials
        add(f"{first[0]}. {' '.join(parts[1:])}")                   # first initial
        add(f"{last}, {' '.join(parts[:-1])}")                      # index order
        add(f"{name} Trust")                                        # trust form
        add(f"{name}, Trustee")                                     # trustee form
        if len(parts) >= 3:
            # possible maiden-name reading: treat middle as maiden surname
            add(f"{first} {' '.join(middles)}")
    return variants


def build_package(party: str, section_township_range: str, county: str, state: str,
                  instrument_types: list | None = None,
                  date_range: str = "inception-present") -> SearchPackage:
    pkg = SearchPackage(
        party=party, section_township_range=section_township_range,
        county=county, state=state,
        name_variants=name_variants(party),
        instrument_types=list(instrument_types or DEFAULT_INSTRUMENT_TYPES),
        date_range=date_range)
    if _is_entity(party):
        pkg.notes.append("entity: also search state SoS records for mergers, "
                         "conversions, and name changes (Move #53)")
    else:
        pkg.notes.append("individual: check probate index and married/maiden "
                         "variants; merge identities only with evidence (Move #57)")
    return pkg


def packages_for_chain(graph, section_township_range: str, county: str,
                       state: str) -> list[SearchPackage]:
    """One package per party involved in a chain break or name near-miss."""
    unresolved: list[str] = []
    for f in graph.analyze():
        if f.rule == "chain_break":
            m = re.search(r"grantor '([^']+)'", f.message)
            if m:
                unresolved.append(m.group(1))
        elif f.rule == "name_near_miss":
            unresolved += re.findall(r"'([^']+)'", f.message)[:2]
    seen: set[str] = set()
    out = []
    for party in unresolved:
        if party.casefold() not in seen:
            seen.add(party.casefold())
            out.append(build_package(party, section_township_range, county, state))
    return out


def render(pkg: SearchPackage) -> str:
    lines = [
        f"SEARCH PACKAGE — {pkg.party}",
        f"  where: {pkg.section_township_range}, {pkg.county} County, {pkg.state}",
        f"  dates: {pkg.date_range}",
        "  names to run:",
    ]
    lines += [f"    - {v}" for v in pkg.name_variants]
    lines.append(f"  instrument types: {', '.join(pkg.instrument_types)}")
    lines += [f"  note: {n}" for n in pkg.notes]
    return "\n".join(lines)
