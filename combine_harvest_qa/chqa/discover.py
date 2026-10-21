"""Rank Drive files per section from a metadata listing (JSON exported from the Drive connector).

The toolkit never talks to Drive itself (no credentials, no network). Feed it the listing:
  {"files":[{"id","title","modifiedTime","owner","parentId","mimeType","fileSize","viewUrl"}...]}
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Iterable

ROLE_PAT = [
    ("blm_index", re.compile(r"blm|WYW-?\d{5,6}.*index|federal", re.I)),
    ("county_index", re.compile(r"(county).*(index)|abstract_index|Penterra_Abstract_Index", re.I)),
    ("checklist", re.compile(r"checklist", re.I)),
    ("letter", re.compile(r"certification|letter", re.I)),
    ("support", re.compile(r"census|crosswalk|findings|locator|appearance|inventory|pull_list|prompt|ledger", re.I)),
    ("package", re.compile(r"\.zip$|package|REVIEW", re.I)),
]
QUALITY_BOOST = [(re.compile(r"OVERTIME|100pct|FINAL", re.I), 3), (re.compile(r"BEST|VERIFIED|QUALIFIED", re.I), 2),
                 (re.compile(r"PREVIEW|UNAPPLIED|TEMP|ROOT_PATCH|draft|old|bak", re.I), -3)]


SECTION_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9])S(?:ec(?:tion)?)?[ _-]?0?(\d{1,2})(?!\d)", re.I),                 # S13_, Sec31, Section 31, Section_31
    re.compile(r"(?<!\d)(\d{1,2})-\d{2}N-\d{2}W", re.I),                                          # 13-45N-76W_...
    re.compile(r"\d{2}N-\d{2}W-0?(\d{1,2})(?!\d)", re.I),                                         # 47N-76W-31_...
]


def section_of(title: str) -> str | None:
    for pat in SECTION_PATTERNS:
        m = pat.search(title)
        if m and 1 <= int(m.group(1)) <= 36:
            return m.group(1).zfill(2)
    return None


def role_of(title: str) -> str:
    for role, pat in ROLE_PAT:
        if pat.search(title):
            return role
    return "other"


def rank(files: Iterable[dict], sections: set[str], me: str | None = None) -> dict:
    out: dict[str, list[dict]] = defaultdict(list)
    for f in files:
        sec = section_of(f["title"])
        if sec is None or sec not in sections or f.get("mimeType") == "application/vnd.google-apps.folder" and False:
            continue
        score = sum(w for pat, w in QUALITY_BOOST if pat.search(f["title"]))
        role = role_of(f["title"])
        size = int(f["fileSize"]) if str(f.get("fileSize") or "").isdigit() else None
        stub = bool(role in ("county_index", "blm_index", "checklist", "letter") and size is not None and size < 3000)
        if stub:
            score -= 5          # a 1 KB "index" is a stub/placeholder regardless of what its name claims
        entry = {"section": sec, "role": role, "title": f["title"], "id": f["id"], "modified": f["modifiedTime"],
                 "owner": f.get("owner"), "foreign_owner": bool(me and f.get("owner") and f["owner"] != me),
                 "size": f.get("fileSize"), "possible_stub": stub, "url": f.get("viewUrl"), "quality_score": score}
        out[sec].append(entry)
    for sec in out:
        out[sec].sort(key=lambda e: (e["role"], -e["quality_score"], e["modified"]), reverse=False)
    return {k: v for k, v in sorted(out.items())}


def best_per_role(ranked: dict) -> dict:
    best: dict[str, dict[str, dict]] = {}
    for sec, items in ranked.items():
        cur: dict[str, dict] = {}
        for e in items:
            k = e["role"]
            if k not in cur or (e["quality_score"], e["modified"]) > (cur[k]["quality_score"], cur[k]["modified"]):
                cur[k] = e
        best[sec] = cur
    return best


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Rank newest/best Drive files per section from a listing JSON")
    ap.add_argument("listing")
    ap.add_argument("--sections", nargs="+", required=True)
    ap.add_argument("--me", help="your account email; files owned by others are flagged")
    ap.add_argument("--since", help="ISO timestamp; only files modified after this")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args(argv)
    files = json.load(open(a.listing, encoding="utf8"))["files"]
    if a.since:
        files = [f for f in files if f["modifiedTime"] >= a.since]
    ranked = rank(files, {s.zfill(2) for s in a.sections}, a.me)
    json.dump({"ranked": ranked, "best_per_role": best_per_role(ranked)}, open(a.out, "w", encoding="utf8"), indent=2)
    print(f"wrote {a.out}: " + ", ".join(f"S{k}={len(v)} files" for k, v in ranked.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
