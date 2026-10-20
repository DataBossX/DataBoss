"""Exact-schema tests, forbidden entries, false Part numbers and physical PDF page references."""
from __future__ import annotations

import posixpath
import re
from typing import Any

from .util import norm_compare, norm_text

PART_IN_NAME = re.compile(r"(?i)^(?P<stem>.*?)[ _\-]*part[ _\-]*(?P<n>\d+)$")
PART_IN_CELL = re.compile(r"(?i)\bpart\s*(?:no\.?\s*)?(\d+)\b")
PAGE_TOKEN = re.compile(r"^\s*(\d+)\s*(?:[-–—]|to)\s*(\d+)\s*$")


def schema_for(kind: str | None, cfg: dict[str, Any]) -> list[str] | None:
    return {"county": cfg["county_schema"], "federal": cfg["federal_schema"]}.get(kind or "")


def test_schema(header: list[str], kind: str | None, cfg: dict[str, Any]) -> dict[str, Any]:
    """Exact comparison: same count, same order, same text after whitespace collapse (case-sensitive)."""
    exp = schema_for(kind, cfg)
    res: dict[str, Any] = {"kind": kind, "exact": False, "expected_count": len(exp) if exp else None,
                           "actual_count": len(header), "issues": []}
    if exp is None:
        res["issues"].append("kind_unknown")
        return res
    h = [norm_text(c) for c in header]
    if h == exp:
        res["exact"] = True
        return res
    if len(h) != len(exp):
        res["issues"].append(f"column_count {len(h)} != {len(exp)}")
    for i, (a, b) in enumerate(zip(h, exp)):
        if a != b:
            tag = "case_only" if a.casefold() == b.casefold() else "mismatch"
            res["issues"].append(f"col{i + 1} {tag}: got {a!r} expected {b!r}")
    if sorted(h) == sorted(exp) and h != exp:
        res["issues"].append("same_columns_wrong_order")
    for extra in h[len(exp):]:
        res["issues"].append(f"extra_column {extra!r}")
    return res


def forbidden_header_hits(header: list[str], cfg: dict[str, Any]) -> list[str]:
    bad = {norm_compare(x) for x in cfg["forbidden_headers"]}
    return [c for c in header if norm_compare(c) in bad]


def forbidden_value_hits(rows: list[list[str]], row_numbers: list[int], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    pats = [re.compile(p) for p in cfg["forbidden_value_patterns"]]
    out = []
    for r, no in zip(rows, row_numbers):
        for ci, c in enumerate(r):
            if any(p.search(c) for p in pats):
                out.append({"row": no, "col": ci + 1, "value": c[:80]})
    return out


def extra_width_rows(rows: list[list[str]], row_numbers: list[int], width: int) -> list[int]:
    return [no for r, no in zip(rows, row_numbers) if any(r[width:])]


def parse_page_refs(text: str) -> tuple[list[int], list[str]]:
    """'5', '5-7', '5, 9', 'pp. 5-7' -> ([5,6,7], []). Unparsable tokens are returned, never guessed."""
    nums: list[int] = []
    bad: list[str] = []
    t = re.sub(r"(?i)\b(pp?|pages?|pgs?)\b\.?", "", text or "")
    for tok in re.split(r"[,;/&]|\band\b", t):
        tok = tok.strip()
        if not tok:
            continue
        m = PAGE_TOKEN.match(tok)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if b < a or b - a > 500:
                bad.append(tok)
            else:
                nums.extend(range(a, b + 1))
        elif tok.isdigit():
            nums.append(int(tok))
        else:
            bad.append(tok)
    return nums, bad


class PdfIndex:
    def __init__(self, entries: list[dict[str, Any]]):
        self.by_name: dict[str, list[dict[str, Any]]] = {}
        self.parts: dict[str, set[int]] = {}
        for e in entries:
            if e["ext"] != ".pdf":
                continue
            base = posixpath.basename(e["path"].split("!/")[-1])
            self.by_name.setdefault(base.casefold(), []).append(e)
            stem = base.rsplit(".", 1)[0]
            m = PART_IN_NAME.match(stem)
            if m:
                self.parts.setdefault(norm_compare(m.group("stem")), set()).add(int(m.group("n")))

    def resolve(self, ref: str) -> list[dict[str, Any]]:
        base = posixpath.basename(ref.replace("\\", "/").strip()).casefold()
        if base and "." not in base:
            base += ".pdf"
        return self.by_name.get(base, [])

    def part_exists(self, source_ref: str, n: int) -> bool:
        base = posixpath.basename(source_ref.replace("\\", "/")).rsplit(".", 1)[0]
        m = PART_IN_NAME.match(base)
        if m:  # the reference itself names a part file
            return int(m.group("n")) == n and bool(self.resolve(source_ref))
        return n in self.parts.get(norm_compare(base), set())


def check_row_refs(row: dict[str, str], pdfs: PdfIndex, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-row evidence findings for source PDF resolution, page range and Part numbers."""
    out: list[dict[str, Any]] = []
    src = norm_text(row.get(cfg["source_pdf_field"], ""))
    page_txt = norm_text(row.get(cfg["pdf_page_field"], ""))
    cands = pdfs.resolve(src) if src else []
    if page_txt or src:
        if src and not cands:
            out.append({"code": "SOURCE_PDF_NOT_FOUND", "detail": src})
        if len({c["sha256"] for c in cands}) > 1:
            out.append({"code": "SOURCE_PDF_AMBIGUOUS", "detail": f"{src}: {len(cands)} differing files share this name"})
        pages, bad = parse_page_refs(page_txt)
        for b in bad:
            out.append({"code": "PAGE_REF_UNPARSABLE", "detail": b})
        if page_txt and not pages and not bad:
            out.append({"code": "PAGE_REF_UNPARSABLE", "detail": page_txt})
        known = [c["pdf_pages"] for c in cands if c.get("pdf_pages")]
        if known and pages:
            limit = max(known)  # lenient when copies differ; ambiguity is flagged separately
            for p in sorted(set(pages)):
                if p < 1 or p > limit:
                    out.append({"code": "PAGE_REF_OUT_OF_RANGE", "detail": f"page {p} not in 1..{limit} of {src}"})
        elif pages and src and cands and not known:
            out.append({"code": "PAGE_COUNT_UNKNOWN", "detail": src})
    for k, v in row.items():
        if k in (cfg["source_pdf_field"],):
            continue
        for m in PART_IN_CELL.finditer(v or ""):
            n = int(m.group(1))
            if not src or not pdfs.part_exists(src, n):
                out.append({"code": "FALSE_PART_NUMBER", "detail": f"'{m.group(0)}' in column {k!r}; no matching part file for {src or '(no source)'}"})
    # a Source PDF cell that itself says "part N" must resolve to an existing part file
    m = PART_IN_NAME.match(posixpath.basename(src.replace("\\", "/")).rsplit(".", 1)[0]) if src else None
    if m and not cands:
        out.append({"code": "FALSE_PART_NUMBER", "detail": f"source names part {m.group('n')} but no such file exists: {src}"})
    return out
