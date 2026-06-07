"""party_and_date_extractor -- normalize parties and dates."""
from __future__ import annotations

import datetime as _dt
import re


def to_short_date(value) -> str:
    """Return M/D/YYYY, or '' if not a parseable date."""
    if value is None or value == "":
        return ""
    if isinstance(value, (_dt.datetime, _dt.date)):
        d = value
        return f"{d.month}/{d.day}/{d.year}"
    s = str(value).strip()
    if not s or s.lower() in {"none", "nan", "nat", "not provided", "not verified"}:
        return ""
    # common formats
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            d = _dt.datetime.strptime(s.split("+")[0].strip(), fmt)
            return f"{d.month}/{d.day}/{d.year}"
        except ValueError:
            continue
    # ISO-ish 'YYYY-MM-DD...'
    m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        y, mo, dy = map(int, m.groups())
        return f"{mo}/{dy}/{y}"
    return s  # leave human text as-is


def split_parties(value) -> list[str]:
    """Split a multi-party cell into clean party names."""
    if value is None:
        return []
    s = str(value)
    # Split on arrows, semicolons and newlines. Commas are NOT separators
    # because entity names embed them (", LLC", ", LP", ", Inc.").
    parts = re.split(r"->|→|;|\n", s)
    out = []
    for p in parts:
        p = p.strip().strip(",")
        if p and p.lower() not in {"public", "none"}:
            out.append(p)
    return out


def grantor_grantee(value) -> tuple[str, str]:
    """For a 'A -> B' party string, return (grantor, grantee)."""
    if value is None:
        return "", ""
    s = str(value)
    if "->" in s or "→" in s:
        left, _, right = re.split(r"->|→", s, maxsplit=1)[0], None, re.split(r"->|→", s, maxsplit=1)[-1]
        return left.strip(), right.strip()
    return s.strip(), ""
