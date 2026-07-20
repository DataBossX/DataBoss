"""Unified mineral / leasehold / working-interest / net-revenue calculator.

This is the economics core the mission asks for:

* **Mineral ownership** -- who owns the minerals, as an exact decimal of the 8/8
  estate, and the resulting *net mineral acres* (NMA = mineral interest x gross
  tract acres).
* **Leasehold / working interest (WI)** -- the cost-bearing operating interest
  created when a mineral owner leases; WI equals the leased mineral fraction.
* **Royalty** -- the cost-free share the lessor reserves in the lease (1/8, 3/16,
  1/5, ...), plus any overriding royalty (ORRI) carved out of a working interest.
* **Net revenue interest (NRI)** -- each party's share of production revenue:
    - working-interest owner:  NRI = leased_mineral x (1 - royalty - ORRI)
    - royalty (lessor) owner:  NRI = mineral x royalty
    - ORRI owner:              NRI = leased_mineral x ORRI

Everything is computed with **exact** :class:`fractions.Fraction` math via
:mod:`horizon.interest` -- never floats -- because a float cannot represent
common mineral fractions (1/3, 3/16, 5/128) and the error compounds into a
fabricated balance across a division of interest.

**No fabrication.** When an input cannot be parsed, the party is emitted with a
``review`` flag and a reason; the calculator never invents a number to make the
8/8 totals close. The two governing identities are *checked and reported*, not
forced:

    sum(mineral interests over a tract)      == 1   (8/8)
    sum(WI over a fully-leased unit)          == 1   (8/8)
    sum(all NRI over a fully-leased unit)     == 1   (8/8)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import List, Optional

# Reuse the exact, unit-tested interest primitives -- do not re-implement them.
from horizon.interest import (
    FULL,
    format_acres,
    format_fraction,
    net_acres,
    try_parse_acres,
    try_parse_interest,
)

# A whole estate is 8/8 == 1. Tolerance is ZERO: these are exact fractions, so a
# division of interest either sums to exactly 1 or it does not. We never accept
# a "close enough" total -- that is exactly the fabrication the mission forbids.
EIGHT_EIGHTHS = FULL

REVIEW = "review"
OK = "ok"


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
@dataclass
class MineralOwner:
    """A mineral owner's undivided share of one tract's 8/8 mineral estate.

    ``mineral_interest`` is any form :func:`horizon.interest.parse_interest`
    accepts: a fraction ("1/2"), decimal ("0.5"), percent ("12.5%"), or
    "x of y". ``royalty`` / ``orri`` / ``lessee`` describe the lease of this
    owner's share (leave ``lessee`` blank for an unleased / open interest).
    """

    name: str
    mineral_interest: str
    royalty: str = ""          # lessor royalty reserved in the lease (e.g. "3/16")
    orri: str = ""             # overriding royalty carved from this WI (optional)
    lessee: str = ""           # operator taking the working interest (blank = unleased)
    source: str = ""           # evidence citation (file / instrument) -- never invented


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
@dataclass
class OwnerResult:
    """One computed row of a mineral / DOI roll-up (all exact fractions)."""

    name: str
    role: str                       # "mineral" | "working_interest" | "royalty" | "orri"
    mineral_interest: Optional[Fraction] = None
    net_mineral_acres: Optional[Fraction] = None
    working_interest: Optional[Fraction] = None
    royalty_rate: Optional[Fraction] = None
    nri: Optional[Fraction] = None
    lessee: str = ""
    status: str = OK
    remarks: str = ""
    source: str = ""

    def display(self) -> dict:
        """Human/report-ready strings; blanks stay blank (never zero-filled)."""
        def fr(f: Optional[Fraction]) -> str:
            return format_fraction(f) if f is not None else ""

        def dec(f: Optional[Fraction], places: int = 8) -> str:
            return format_acres(f, places) if f is not None else ""

        return {
            "name": self.name,
            "role": self.role,
            "lessee": self.lessee,
            "mineral_interest": fr(self.mineral_interest),
            "mineral_decimal": dec(self.mineral_interest),
            "net_mineral_acres": (format_acres(self.net_mineral_acres, 4)
                                  if self.net_mineral_acres is not None else ""),
            "working_interest": dec(self.working_interest),
            "royalty_rate": fr(self.royalty_rate),
            "nri": dec(self.nri),
            "status": self.status,
            "remarks": self.remarks,
            "source": self.source,
        }


@dataclass
class TractOwnership:
    """The full ownership + economics roll-up for one tract."""

    tract: str
    gross_acres: Optional[Fraction]
    mineral_rows: List[OwnerResult] = field(default_factory=list)
    doi_rows: List[OwnerResult] = field(default_factory=list)
    defects: List[str] = field(default_factory=list)

    # -- exact totals (never rounded) --------------------------------------
    @property
    def total_mineral(self) -> Fraction:
        return sum((r.mineral_interest for r in self.mineral_rows
                    if r.mineral_interest is not None), Fraction(0))

    @property
    def total_working_interest(self) -> Fraction:
        return sum((r.working_interest for r in self.doi_rows
                    if r.role == "working_interest" and r.working_interest is not None),
                   Fraction(0))

    @property
    def total_nri(self) -> Fraction:
        return sum((r.nri for r in self.doi_rows if r.nri is not None), Fraction(0))

    @property
    def leased_mineral(self) -> Fraction:
        return sum((r.mineral_interest for r in self.mineral_rows
                    if r.mineral_interest is not None and r.lessee), Fraction(0))

    @property
    def needs_review(self) -> bool:
        return bool(self.defects) or any(
            r.status == REVIEW for r in self.mineral_rows + self.doi_rows
        )


# ---------------------------------------------------------------------------
# Direct calculators (the textbook identities, exact)
# ---------------------------------------------------------------------------
def mineral_net_acres(mineral_interest, gross_acres) -> Optional[Fraction]:
    """Net mineral acres = mineral interest x gross acres (exact), or ``None``
    when either input is unparseable (never guessed)."""
    mi = try_parse_interest(mineral_interest)
    ga = try_parse_acres(gross_acres)
    if mi is None or ga is None:
        return None
    return net_acres(mi, ga)


def royalty_nri(mineral_interest, royalty_rate) -> Optional[Fraction]:
    """A royalty owner's NRI = mineral interest x royalty rate (exact)."""
    mi = try_parse_interest(mineral_interest)
    r = try_parse_interest(royalty_rate)
    if mi is None or r is None:
        return None
    return mi * r


def working_interest_nri(working_interest, royalty_rate, orri=0) -> Optional[Fraction]:
    """A working-interest owner's NRI = WI x (1 - royalty - ORRI), exact.

    Returns ``None`` if an input is unparseable. The caller is responsible for
    flagging a *negative* result (burdens exceeding 8/8) -- we return the exact
    value so the defect is visible rather than clamped away.
    """
    wi = try_parse_interest(working_interest)
    r = try_parse_interest(royalty_rate)
    o = try_parse_interest(orri) if str(orri).strip() else Fraction(0)
    if wi is None or r is None or o is None:
        return None
    return wi * (FULL - r - o)


# ---------------------------------------------------------------------------
# Roll-ups
# ---------------------------------------------------------------------------
def mineral_summary(owners: List[MineralOwner], gross_acres,
                    tract: str = "") -> TractOwnership:
    """Compute the mineral-ownership roll-up for one tract.

    Produces one :class:`OwnerResult` per owner (mineral interest + NMA) and
    checks that the mineral estate sums to exactly 8/8 -- reporting a defect if
    it does not, rather than normalizing the numbers.
    """
    ga = try_parse_acres(gross_acres) if str(gross_acres).strip() else None
    out = TractOwnership(tract=tract, gross_acres=ga)
    if str(gross_acres).strip() and ga is None:
        out.defects.append(f"Gross acreage {gross_acres!r} is unparseable; "
                           "net mineral acres not computed.")

    for o in owners:
        mi = try_parse_interest(o.mineral_interest)
        row = OwnerResult(name=o.name, role="mineral", lessee=o.lessee, source=o.source)
        if mi is None:
            row.status = REVIEW
            row.remarks = f"Mineral interest {o.mineral_interest!r} unparseable"
        else:
            row.mineral_interest = mi
            if ga is not None:
                row.net_mineral_acres = mi * ga
        out.mineral_rows.append(row)

    _check_eighths(out, out.total_mineral, "Mineral interests",
                   only_if_all_known=all(r.mineral_interest is not None
                                         for r in out.mineral_rows) and bool(out.mineral_rows))
    _check_duplicate_owners(out, owners)
    return out


def _norm_owner(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(name or "").lower()).strip()


def _check_duplicate_owners(out: TractOwnership, owners: List[MineralOwner]) -> None:
    """Flag the same owner listed more than once in a tract (possible double count)."""
    seen: dict = {}
    for o in owners:
        key = _norm_owner(o.name)
        if not key:
            continue
        seen[key] = seen.get(key, 0) + 1
    for key, n in seen.items():
        if n > 1:
            out.defects.append(
                f"Owner {key!r} is listed {n} times in tract {out.tract!r}; "
                "verify this is intentional and not a double-counted interest.")


def division_of_interest(owners: List[MineralOwner], gross_acres,
                         tract: str = "") -> TractOwnership:
    """Compute the full division of interest (WI, royalty, ORRI, NRI) for a tract.

    Each leased mineral owner expands into up to three DOI rows:

    * a **working-interest** row for the lessee  (WI = leased mineral fraction;
      NRI = mineral x (1 - royalty - ORRI)),
    * a **royalty** row for the lessor            (NRI = mineral x royalty),
    * an **ORRI** row when an override is present  (NRI = mineral x ORRI).

    Unleased mineral owners are carried as an open **mineral** row so the unit's
    accounting stays complete. The unit's WI and NRI totals are checked against
    8/8 (of the leased fraction) and any shortfall/overage is reported as a
    defect -- never silently balanced.
    """
    out = mineral_summary(owners, gross_acres, tract=tract)
    # Start DOI from the mineral rows so an unparseable mineral interest still
    # surfaces (as an open, review-flagged mineral row) in the DOI view.
    by_name = {id(o): r for o, r in zip(owners, out.mineral_rows)}

    for o in owners:
        mrow = by_name[id(o)]
        mi = mrow.mineral_interest
        if not str(o.lessee).strip():
            # Unleased / open interest -- carry the mineral row into the DOI.
            open_row = OwnerResult(
                name=o.name, role="mineral", mineral_interest=mi,
                net_mineral_acres=mrow.net_mineral_acres, lessee="",
                status=mrow.status if mi is not None else REVIEW,
                remarks=(mrow.remarks or "Unleased / open mineral interest"),
                source=o.source,
            )
            out.doi_rows.append(open_row)
            continue

        r = try_parse_interest(o.royalty) if str(o.royalty).strip() else None
        orri = try_parse_interest(o.orri) if str(o.orri).strip() else Fraction(0)

        # Working-interest row (the lessee operates this owner's leased share).
        wi_row = OwnerResult(name=o.lessee, role="working_interest",
                             working_interest=mi, lessee=o.lessee, source=o.source)
        if mi is None:
            wi_row.status = REVIEW
            wi_row.remarks = "Working interest undetermined: mineral interest unparseable"
        elif r is None:
            wi_row.status = REVIEW
            wi_row.remarks = f"Royalty {o.royalty!r} unparseable; NRI not computed"
        elif orri is None:
            wi_row.status = REVIEW
            wi_row.remarks = f"ORRI {o.orri!r} unparseable; NRI not computed"
        else:
            wi_row.royalty_rate = r
            nri = mi * (FULL - r - orri)
            wi_row.nri = nri
            if nri < 0:
                wi_row.status = REVIEW
                wi_row.remarks = (f"Burdens exceed 8/8 (royalty {format_fraction(r)}"
                                  f" + ORRI {format_fraction(orri)}); negative NRI")
        out.doi_rows.append(wi_row)

        # Royalty row (the lessor's reserved, cost-free share).
        ro_row = OwnerResult(name=o.name, role="royalty", royalty_rate=r,
                             lessee=o.lessee, source=o.source)
        if mi is not None and r is not None:
            ro_row.nri = mi * r
        else:
            ro_row.status = REVIEW
            ro_row.remarks = "Royalty NRI undetermined (mineral or royalty unparseable)"
        out.doi_rows.append(ro_row)

        # ORRI row (only when an override is actually present).
        if str(o.orri).strip():
            or_row = OwnerResult(name=f"{o.lessee} (ORRI)", role="orri",
                                 lessee=o.lessee, source=o.source)
            if mi is not None and orri is not None:
                or_row.nri = mi * orri
            else:
                or_row.status = REVIEW
                or_row.remarks = "ORRI NRI undetermined"
            out.doi_rows.append(or_row)

    _check_excessive_burdens(out, owners)
    _rollup_checks(out)
    return out


def _check_excessive_burdens(out: TractOwnership, owners: List[MineralOwner]) -> None:
    """Flag any lease whose royalty + ORRI equals or exceeds 8/8 (impossible)."""
    for o in owners:
        if not str(o.lessee).strip():
            continue
        r = try_parse_interest(o.royalty) if str(o.royalty).strip() else Fraction(0)
        orri = try_parse_interest(o.orri) if str(o.orri).strip() else Fraction(0)
        if r is None or orri is None:
            continue  # unparseable already flagged on the row
        if r + orri >= FULL:
            out.defects.append(
                f"Lease burdens for {o.name!r} in tract {out.tract!r} "
                f"(royalty {format_fraction(r)} + ORRI {format_fraction(orri)} "
                f"= {format_fraction(r + orri)}) equal or exceed 8/8, leaving the "
                "working interest no net revenue. Verify the lease terms.")


# ---------------------------------------------------------------------------
# Invariant checks (report, never force)
# ---------------------------------------------------------------------------
def _check_eighths(out: TractOwnership, total: Fraction, label: str,
                   only_if_all_known: bool) -> None:
    if not only_if_all_known:
        out.defects.append(
            f"{label} cannot be summed to 8/8: one or more values are missing "
            "or unparseable (flagged for examiner review).")
        return
    if total != EIGHT_EIGHTHS:
        diff = total - EIGHT_EIGHTHS
        sign = "over" if diff > 0 else "under"
        out.defects.append(
            f"{label} sum to {format_fraction(total)} "
            f"({format_acres(total, 6)}), not 8/8 -- {sign} by "
            f"{format_fraction(abs(diff))}. Do not release until reconciled.")


def _rollup_checks(out: TractOwnership) -> None:
    """Check the WI and NRI totals against the *leased* fraction of the unit."""
    leased = out.leased_mineral
    if leased == 0:
        return  # nothing leased; DOI totals are trivially the open mineral estate

    all_wi_known = all(
        r.working_interest is not None
        for r in out.doi_rows if r.role == "working_interest")
    if all_wi_known and out.total_working_interest != leased:
        out.defects.append(
            f"Working interest sums to {format_acres(out.total_working_interest, 6)} "
            f"but the leased mineral estate is {format_acres(leased, 6)} -- WI must "
            "equal the leased fraction.")

    # NRI over the leased portion must equal the leased fraction (every leased
    # 8/8 of minerals is fully distributed across WI + royalty + ORRI).
    leased_nri = sum((r.nri for r in out.doi_rows
                      if r.role != "mineral" and r.nri is not None), Fraction(0))
    all_nri_known = all(
        r.nri is not None for r in out.doi_rows if r.role != "mineral")
    if all_nri_known and leased_nri != leased:
        out.defects.append(
            f"NRI over the leased estate sums to {format_acres(leased_nri, 6)} "
            f"but should equal the leased fraction {format_acres(leased, 6)}.")
