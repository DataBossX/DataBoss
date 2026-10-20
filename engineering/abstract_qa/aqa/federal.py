"""Canonical federal instrument ledger for shared federal serials (e.g. WYW).

Consistent events are consolidated; disagreeing fields are listed as candidates and the event is
marked NEEDS_IMAGE_REVIEW. No value is ever chosen over another.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

from .util import norm_compare, norm_text


def normalise_serial(raw: str, cfg: dict[str, Any]) -> str | None:
    m = re.search(cfg["serial_regex"], norm_text(raw))
    if not m:
        return None
    return f"{cfg['serial_prefix']}{int(m.group(1)):d}"


def build_ledger(rows: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    sf, df, tf = cfg["federal_serial_field"], cfg["federal_date_field"], cfg["federal_type_field"]
    events: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    bad_serial: list[dict[str, Any]] = []
    for r in rows:
        if r["kind"] != "federal":
            continue
        f = r["fields"]
        s = normalise_serial(f.get(sf, ""), cfg)
        if s is None:
            bad_serial.append({"section": r["section"], "file": r["file"], "row": r["row_no"], "raw": f.get(sf, "")})
            continue
        events[(s, norm_compare(f.get(df, "")), norm_compare(f.get(tf, "")))].append(r)

    ledger: list[dict[str, Any]] = []
    fields_all = list(cfg["federal_schema"])
    for (serial, d, t), rs in sorted(events.items()):
        secs = sorted({r["section"] for r in rs})
        entry: dict[str, Any] = {
            "ledger_id": hashlib.sha1(f"{serial}|{d}|{t}".encode()).hexdigest()[:12],
            "serial": serial, "sections": secs, "appearances": len(rs), "fields": {}, "conflicts": {},
        }
        for fld in fields_all:
            if fld == sf:
                entry["fields"][fld] = serial
                continue
            vals: dict[str, list[str]] = defaultdict(list)
            for r in rs:
                v = norm_text(r["fields"].get(fld, ""))
                if v:
                    vals[norm_compare(v)].append(v)
            if len(vals) > 1:
                entry["conflicts"][fld] = {k: sorted(set(v)) for k, v in sorted(vals.items())}
                entry["fields"][fld] = ""
            elif vals:
                entry["fields"][fld] = sorted(next(iter(vals.values())))[0]
            else:
                entry["fields"][fld] = ""
        entry["status"] = "NEEDS_IMAGE_REVIEW" if entry["conflicts"] else "CONSISTENT_ACROSS_SECTIONS"
        ledger.append(entry)

    # same serial + type but different dates: possible date conflict (or distinct events); review only
    by_st: dict[tuple[str, str], set[str]] = defaultdict(set)
    for (s, d, t) in events:
        by_st[(s, t)].add(d)
    date_flags = [{"serial": s, "event_type": t, "dates": sorted(ds)} for (s, t), ds in sorted(by_st.items()) if len(ds) > 1]
    return {"ledger": ledger, "unparsed_serial_rows": bad_serial, "possible_date_conflicts": date_flags,
            "serials": len({e["serial"] for e in ledger})}
