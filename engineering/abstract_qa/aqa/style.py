"""Package-style fingerprints compared with the donor section and owner overrides."""
from __future__ import annotations

import posixpath
import re
from typing import Any

from .util import norm_text


def fingerprint(rec: dict[str, Any]) -> dict[str, Any]:
    base = posixpath.basename(rec["file"].split("!/")[-1]).rsplit(".", 1)[0]
    pat = re.sub(r"\d+", "#", re.sub(re.escape(rec["section"]), "{SEC}", base, flags=re.I)) if rec["section"] else base
    meta = rec.get("file_meta", {})
    fp: dict[str, Any] = {
        "ext": rec["ext"], "name_pattern": pat.casefold(), "column_count": len(rec["header"]),
        "header": [norm_text(h) for h in rec["header"]], "table_name": rec["table"] if rec["ext"] != ".docx" else "",
        "sheet_count": len(meta.get("sheets", [])) or None,
    }
    if rec["ext"] == ".docx":
        for k in ("paragraph_styles", "table_styles", "orientation", "margins_in", "table_count"):
            fp[f"docx_{k}"] = meta.get(k)
    fmt = (meta.get("format") or {}).get(rec["table"])
    if fmt:
        for k, v in fmt.items():
            fp[f"xlsx_{k}"] = v
    return fp


def compare_to_donor(selected: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    donor = cfg.get("donor_section")
    fps: dict[tuple[str, str], dict[str, Any]] = {}
    for r in selected:
        fps[(r["section"], r["kind"] or "")] = fingerprint(r)
    out: dict[str, Any] = {"donor_section": donor, "sections": [], "donor_missing": False}
    if not donor:
        out["note"] = "no donor_section configured; fingerprints recorded only"
    donor_fps = {k[1]: v for k, v in fps.items() if k[0] == donor}
    if donor and not donor_fps:
        out["donor_missing"] = True
    for (sec, kind), fp in sorted(fps.items()):
        row: dict[str, Any] = {"section": sec, "kind": kind, "fingerprint": fp, "deviations": []}
        if donor and sec != donor and kind in donor_fps:
            allow = set(cfg["owner_overrides"].get(sec, {}).get("allow", []))
            allow_all = "*" in allow
            for k in sorted(set(fp) | set(donor_fps[kind])):
                if fp.get(k) != donor_fps[kind].get(k):
                    state = "owner_override" if (allow_all or k in allow) else "unexplained"
                    row["deviations"].append({"key": k, "donor": donor_fps[kind].get(k), "section": fp.get(k), "state": state})
        elif donor and sec != donor:
            row["deviations"].append({"key": "kind", "donor": None, "section": kind, "state": "no_donor_counterpart"})
        out["sections"].append(row)
    return out
