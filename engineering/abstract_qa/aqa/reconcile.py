"""Identity-keyed reconciliation across competing section branches. Never positional."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .util import norm_compare, norm_text

_BOOKPAGE = re.compile(r"(?:book|bk|vol(?:ume)?)\.?\s*(\d+)\D+?(?:page|pg|p)\.?\s*(\d+)")
_SLASH = re.compile(r"^\s*(\d+)\s*[/\-]\s*(\d+)\s*$")
_YEARSEQ = re.compile(r"(?<!\d)((?:18|19|20)\d{2})\s*[-/]\s*0*(\d{3,})(?!\d)")
_DIGITS = re.compile(r"\d+")


def recorder_identity(raw: str, county: str = "") -> str | None:
    """Normalise a recorder reference to a stable key, or None if it cannot be keyed.

    Book/Page -> B<book>P<page>; Year-Seq -> R<year>-<seq>; bare number -> N<n>.
    Different reference styles are deliberately NOT cross-mapped; that needs image review.
    """
    t = norm_text(raw).casefold()
    if not t:
        return None
    c = norm_compare(county)
    m = _BOOKPAGE.search(t)
    if m:
        return f"{c}|B{int(m.group(1))}P{int(m.group(2))}"
    m = _YEARSEQ.search(t)
    if m:
        return f"{c}|R{m.group(1)}-{int(m.group(2))}"
    m = _SLASH.match(t)
    if m:
        return f"{c}|B{int(m.group(1))}P{int(m.group(2))}"
    nums = _DIGITS.findall(t)
    if len(nums) == 1:
        return f"{c}|N{int(nums[0])}"
    return None


def reconcile(rows: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    group_of = {s: g for g, members in cfg["branch_groups"].items() for s in members}
    rid = cfg["recorder_id_field"]
    ids: dict[str, list[dict[str, Any]]] = defaultdict(list)
    no_identity: list[dict[str, Any]] = []
    for r in rows:
        if r["kind"] != "county":
            continue
        county = r.get("county") or cfg["county_default"]
        key = recorder_identity(r["fields"].get(rid, ""), county)
        r["identity"] = key
        if key is None:
            no_identity.append({"section": r["section"], "file": r["file"], "row": r["row_no"],
                                "raw": r["fields"].get(rid, "")})
        else:
            ids[key].append(r)

    sections_with_rows: dict[str, set[str]] = defaultdict(set)   # section -> identities
    tracts_in_section: dict[str, set[str]] = defaultdict(set)
    for key, rs in ids.items():
        for r in rs:
            sections_with_rows[r["section"]].add(key)
            tracts_in_section[r["section"]].add(norm_compare(r["fields"].get(cfg["tract_field"], "")))
    # sections that contributed only unkeyed rows still exist
    for r in rows:
        if r["kind"] == "county":
            sections_with_rows.setdefault(r["section"], set())

    identities, conflicts, repetitions, dups = [], [], [], []
    for key in sorted(ids):
        rs = ids[key]
        secs = sorted({r["section"] for r in rs})
        tracts = sorted({norm_compare(r["fields"].get(cfg["tract_field"], "")) for r in rs} - {""})
        identities.append({"identity": key, "sections": secs, "appearances": len(rs), "tracts": tracts})
        # true duplicates: same section + same tract + same identity more than once
        seen: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for r in rs:
            seen[(r["section"], norm_compare(r["fields"].get(cfg["tract_field"], "")))].append(r)
        for (sec, tr), g in sorted(seen.items()):
            if len(g) > 1:
                dups.append({"identity": key, "section": sec, "tract": tr, "count": len(g),
                             "locations": [f"{x['file']}#{x['table']}:{x['row_no']}" for x in g]})
        # field conflicts, per compare field, across every appearance
        field_conf = []
        for f in cfg["compare_fields"]:
            vals: dict[str, list[str]] = defaultdict(list)
            for r in rs:
                v = r["fields"].get(f)
                if v is None:
                    continue
                n = norm_compare(v)
                if n:
                    vals[n].append(f"{r['section']}:{v}")
            if len(vals) > 1:
                field_conf.append({"field": f, "values": {k: sorted(set(v)) for k, v in sorted(vals.items())}})
        if field_conf:
            conflicts.append({"identity": key, "sections": secs, "conflicts": field_conf,
                              "status": "NEEDS_IMAGE_REVIEW"})
        if len(secs) > 1:
            repetitions.append({"identity": key, "sections": secs, "fields_agree": not field_conf,
                                "classification": "legitimate_cross_section_repetition" if not field_conf
                                else "repetition_with_field_conflict"})

    candidate_missing = []
    populations = []
    for g, members in sorted(cfg["branch_groups"].items()):
        present = [s for s in sorted(members) if s in sections_with_rows]
        union = set().union(*(sections_with_rows[s] for s in present)) if present else set()
        for s in present:
            populations.append({"group": g, "section": s, "identities": len(sections_with_rows[s]),
                                "group_union": len(union)})
        if len(present) < 2:
            continue
        for key in sorted(union):
            have = {s for s in present if key in sections_with_rows[s]}
            for s in present:
                if s in have:
                    continue
                id_tracts = {norm_compare(r["fields"].get(cfg["tract_field"], "")) for r in ids[key]} - {""}
                overlap = bool(id_tracts & tracts_in_section[s])
                candidate_missing.append({
                    "group": g, "identity": key, "missing_in": s, "present_in": sorted(have),
                    "classification": "probable_omission_same_tract_present" if overlap
                    else "may_be_legitimate_tract_not_in_section",
                    "status": "NEEDS_IMAGE_REVIEW"})
    hazards = []
    for g, members in sorted(cfg["branch_groups"].items()):
        pres = [s for s in sorted(members) if s in sections_with_rows]
        for i, a in enumerate(pres):
            for b in pres[i + 1:]:
                A, B = sections_with_rows[a], sections_with_rows[b]
                if A != B:
                    hazards.append({"group": g, "a": a, "b": b, "only_a": len(A - B), "only_b": len(B - A),
                                    "shared": len(A & B),
                                    "note": "populations differ; positional merge would corrupt"})
    return {
        "identities": identities, "conflicts": conflicts, "repetitions": repetitions,
        "within_section_duplicates": dups, "candidate_missing": candidate_missing,
        "no_identity_rows": no_identity, "populations": populations, "branch_divergence": hazards,
    }
