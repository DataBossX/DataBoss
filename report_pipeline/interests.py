"""Deterministic mineral/royalty interest calculations.

Computes interests ONLY where the source data is sufficient. When an input is
missing, the result is left blank and flagged 'insufficient_data:<what>' — it is
never guessed. Every computed value carries the formula used, so it is auditable.

Standard relationships:
  net mineral acres = gross acres x mineral interest (fraction)
  decimal interest  = (net acres / unit acres) x royalty
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


def parse_number(raw: Any) -> Optional[float]:
    """Parse a fraction ('3/16'), percent ('12.5%'), or decimal ('0.5000', '1,280')."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if not s:
        return None
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", s)
    if m:
        denom = float(m.group(2))
        return float(m.group(1)) / denom if denom else None
    if s.endswith("%"):
        try:
            return float(s[:-1].replace(",", "")) / 100.0
        except ValueError:
            return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def net_mineral_acres(gross_acres: Any, mineral_interest: Any) -> Tuple[Optional[float], str]:
    g = parse_number(gross_acres)
    mi = parse_number(mineral_interest)
    missing = [n for n, v in (("gross_acres", g), ("mineral_interest", mi)) if v is None]
    if missing:
        return None, "insufficient_data:" + ",".join(missing)
    return round(g * mi, 4), f"net_acres = {g} x {mi}"


def decimal_interest(net_acres: Any, unit_acres: Any, royalty: Any) -> Tuple[Optional[float], str]:
    na = parse_number(net_acres)
    ua = parse_number(unit_acres)
    ro = parse_number(royalty)
    missing = [n for n, v in (("net_acres", na), ("unit_acres", ua), ("royalty", ro)) if v is None]
    if missing:
        return None, "insufficient_data:" + ",".join(missing)
    if ua == 0:
        return None, "invalid:unit_acres=0"
    return round((na / ua) * ro, 8), f"decimal = ({na}/{ua}) x {ro}"


def compute_row(fact: Dict[str, Any], unit_acres: Any = None) -> Dict[str, Any]:
    """Produce an interest-calculation row for one extracted fact."""
    gross = fact.get("gross_acres")
    net = fact.get("net_acres")
    mineral = fact.get("mineral_interest")
    royalty = fact.get("royalty")
    provided_decimal = fact.get("decimal_interest")

    review: List[str] = []
    computed_net, net_note = net_mineral_acres(gross, mineral)
    if computed_net is None and not net:
        review.append(net_note)
    net_for_decimal = net or computed_net

    computed_decimal, dec_note = decimal_interest(net_for_decimal, unit_acres, royalty)
    if computed_decimal is None:
        review.append(dec_note)

    # Cross-check computed vs source-provided decimal, if both exist.
    provided = parse_number(provided_decimal)
    mismatch = ""
    if provided is not None and computed_decimal is not None:
        if abs(provided - computed_decimal) > 0.0005:
            mismatch = f"DECIMAL MISMATCH: source={provided} computed={computed_decimal}"
            review.append(mismatch)

    return {
        "relpath": fact.get("relpath", ""),
        "source_file": fact.get("source_file", ""),
        "gross_acres": gross or "",
        "mineral_interest": mineral or "",
        "net_acres_source": net or "",
        "net_acres_computed": "" if computed_net is None else computed_net,
        "unit_acres": unit_acres or "",
        "royalty": royalty or "",
        "decimal_source": provided_decimal or "",
        "decimal_computed": "" if computed_decimal is None else computed_decimal,
        "net_formula": net_note,
        "decimal_formula": dec_note,
        "review_flag": ";".join(r for r in review if r) or "",
    }


FIELDS = ["relpath", "source_file", "gross_acres", "mineral_interest", "net_acres_source",
          "net_acres_computed", "unit_acres", "royalty", "decimal_source", "decimal_computed",
          "net_formula", "decimal_formula", "review_flag"]
