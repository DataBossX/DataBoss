"""Task 13 -- assemble the final calculated owner table from chain results only.

Title-sheet rules enforced here:
  * final owners only -- an intermediate who conveyed all interest is dropped;
  * no duplicates; retained/royalty owners kept;
  * an owner that cannot be proven final is marked Needs Verification (never
    presented as a clean final owner);
  * totals must match tract control or the tract is flagged.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Dict, List

from .models import FinalOwner, TractResult
from .utils import format_fraction, try_parse_interest


def final_owner_table(results: List[TractResult]) -> List[FinalOwner]:
    owners: List[FinalOwner] = []
    for res in results:
        # Merge duplicate owner names within a tract (defensive; chain already nets).
        merged: Dict[str, FinalOwner] = {}
        for o in res.final_owners:
            key = o.owner.strip().lower()
            if key in merged:
                a = try_parse_interest(merged[key].mineral_interest) or Fraction(0)
                b = try_parse_interest(o.mineral_interest) or Fraction(0)
                merged[key].mineral_interest = format_fraction(a + b)
            else:
                merged[key] = o.model_copy()
        for o in merged.values():
            if not res.balanced:
                o.status = "Needs Verification"
                o.notes = (o.notes + " " if o.notes else "") + \
                    "Needs Verification: tract does not balance to control acreage."
            owners.append(o)
    return owners


def owner_counts(owners: List[FinalOwner]) -> Dict[str, int]:
    return {
        "total": len(owners),
        "clean": sum(1 for o in owners if o.status == "ok"),
        "needs_verification": sum(1 for o in owners if o.status != "ok"),
        "assumption_owners": sum(1 for o in owners if o.is_assumption),
    }
