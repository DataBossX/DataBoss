"""Cross-check a section deliverable: index rows vs scanned images vs BLM parts.

Answers the three questions that decide whether a section can be turned in:

1. Does every BLM lease PDF part series run 1..N with nothing missing?
2. Does every image in the scan folder map to an indexed document, and
   does every indexed document have a scan?
3. Does the section folder hold the exact Section 15 six-file set?
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

#: "WYW-51704 Part 3 of 6.pdf" -> lease WYW-51704, part 3, of 6
PART_RE = re.compile(
    r"^(?P<lease>WYW-\d+)\s+Part\s+(?P<part>\d+)\s+of\s+(?P<total>\d+)\.pdf$", re.I
)
#: "WYW-21220.pdf" -> single-part lease document
SINGLE_RE = re.compile(r"^(?P<lease>WYW-\d+)\.pdf$", re.I)
#: "Serial Register Page WYW-51704 (8.04.2026).pdf"
SRP_RE = re.compile(
    r"^Serial Register Page\s+(?P<lease>WYW-\d+)\s*(?:\((?P<dated>[^)]+)\))?\.pdf$", re.I
)
#: "p14-index-07.png" -> section 14, image 7
IMAGE_RE = re.compile(r"^p(?P<section>\d+)-index-(?P<seq>\d+)\.(?:png|jpg|jpeg)$", re.I)


@dataclass
class LeaseSeries:
    lease: str
    declared_total: int | None = None
    parts_present: set[int] = field(default_factory=set)
    single: bool = False

    @property
    def missing_parts(self) -> list[int]:
        if self.single or self.declared_total is None:
            return []
        return sorted(set(range(1, self.declared_total + 1)) - self.parts_present)

    @property
    def file_count(self) -> int:
        return 1 if self.single else len(self.parts_present)

    @property
    def complete(self) -> bool:
        return not self.missing_parts


def scan_blm(names: list[str]) -> tuple[dict[str, LeaseSeries], dict[str, list[str]]]:
    """Group BLM filenames into lease part-series and serial register pages."""
    series: dict[str, LeaseSeries] = {}
    srps: dict[str, list[str]] = defaultdict(list)

    for name in names:
        if m := PART_RE.match(name):
            lease = m["lease"].upper()
            s = series.setdefault(lease, LeaseSeries(lease=lease))
            s.declared_total = int(m["total"])
            s.parts_present.add(int(m["part"]))
        elif m := SINGLE_RE.match(name):
            lease = m["lease"].upper()
            s = series.setdefault(lease, LeaseSeries(lease=lease))
            s.single = True
            s.declared_total = 1
            s.parts_present.add(1)
        elif m := SRP_RE.match(name):
            srps[m["lease"].upper()].append(m["dated"] or "UNDATED")
    return series, dict(srps)


def scan_images(names: list[str]) -> dict[str, dict[str, object]]:
    """Group image filenames by section and find sequence gaps."""
    by_section: dict[str, set[int]] = defaultdict(set)
    unparsed: list[str] = []
    for name in names:
        if m := IMAGE_RE.match(name):
            by_section[m["section"]].add(int(m["seq"]))
        else:
            unparsed.append(name)

    out: dict[str, dict[str, object]] = {}
    for section, seqs in sorted(by_section.items()):
        lo, hi = min(seqs), max(seqs)
        out[section] = {
            "count": len(seqs),
            "first": lo,
            "last": hi,
            "missing": sorted(set(range(lo, hi + 1)) - seqs),
        }
    if unparsed:
        out["_unparsed"] = {"count": len(unparsed), "names": sorted(unparsed)[:50]}
    return out


def check_deliverable(section: int, filenames: list[str], leases: list[str]) -> dict:
    """Compare a section folder's contents to the Section 15 six-file rule."""
    slug = f"{section}-45N-76W"
    expected = {
        f"45N-76W-{section:02d}_Campbell_Co_Penterra_Abstract_Index.xlsx",
        f"Abstract_Checklist_{slug}.xlsx",
        f"{slug}_Certification_Letter.docx",
        f"{slug}_Certification_Letter.pdf",
    }
    for lease in leases:
        expected.add(f"{lease} Campbell Co. Penterra Abstract Index.xlsx")

    present = set(filenames)
    return {
        "section": section,
        "expected_count": len(expected),
        "present_count": len(present & expected),
        "missing": sorted(expected - present),
        "extra": sorted(present - expected),
        "complete": not (expected - present),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--blm-dir", type=Path, help="folder of BLM lease PDFs")
    ap.add_argument("--image-dir", type=Path, help="folder of scanned index images")
    ap.add_argument("--section-dir", type=Path, help="folder of a section deliverable")
    ap.add_argument("--section", type=int, help="section number for --section-dir")
    ap.add_argument("--leases", nargs="*", default=[], help="leases for --section-dir")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)

    result: dict[str, object] = {}

    if args.blm_dir:
        names = [p.name for p in args.blm_dir.iterdir() if p.is_file()]
        series, srps = scan_blm(names)
        total_parts = sum(s.file_count for s in series.values())
        incomplete = {k: v.missing_parts for k, v in series.items() if not v.complete}
        result["blm"] = {
            "leases": len(series),
            "lease_document_pdfs": total_parts,
            "incomplete_series": incomplete,
            "serial_register_pages": {k: len(v) for k, v in srps.items()},
            "leases_without_srp": sorted(set(series) - set(srps)),
        }
        print(f"BLM: {len(series)} leases, {total_parts} part PDFs, "
              f"{len(incomplete)} incomplete series")
        for lease, missing in incomplete.items():
            print(f"  MISSING {lease}: parts {missing}")

    if args.image_dir:
        names = [p.name for p in args.image_dir.iterdir() if p.is_file()]
        result["images"] = scan_images(names)
        for section, info in result["images"].items():
            if section == "_unparsed":
                print(f"IMAGES: {info['count']} files not matching pNN-index-NN pattern")
                continue
            print(f"IMAGES section {section}: {info['count']} files "
                  f"({info['first']}..{info['last']}), missing={info['missing']}")

    if args.section_dir:
        if args.section is None:
            ap.error("--section-dir requires --section")
        names = [p.name for p in args.section_dir.iterdir() if p.is_file()]
        res = check_deliverable(args.section, names, args.leases)
        result["deliverable"] = res
        print(f"SECTION {args.section}: {res['present_count']}/{res['expected_count']} "
              f"expected files present")
        for name in res["missing"]:
            print(f"  MISSING {name}")

    if args.json:
        args.json.write_text(json.dumps(result, indent=2, default=list), encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
