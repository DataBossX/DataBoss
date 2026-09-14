"""PDF page/part census. Counts physical pages without a third-party library.

Page count is taken from the PDF object graph (/Type /Page), then cross-checked
against /Count on the page-tree root. A disagreement is reported, never guessed.
"""
from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path

_PART = re.compile(r"Part\s+(\d+)\s+of\s+(\d+)", re.I)
_SERIAL = re.compile(r"(WYW)[\s-]*0*(\d{4,6})", re.I)
_SRP = re.compile(r"serial\s*register\s*page", re.I)


def parse_part(name: str) -> tuple[int | None, int | None]:
    m = _PART.search(name)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def parse_serial(name: str) -> str | None:
    m = _SERIAL.search(name)
    return f"WYW-{int(m.group(2)):06d}" if m else None


def is_srp(name: str) -> bool:
    return bool(_SRP.search(name))


def count_pages(path: str | Path) -> dict:
    """Return {'pages', 'declared', 'agree'} for a PDF on disk."""
    data = Path(path).read_bytes()
    # Expand object streams so /Type/Page inside them is visible.
    blobs = [data]
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end == -1:
            continue
        try:
            blobs.append(zlib.decompress(data[start:end]))
        except zlib.error:
            pass
    joined = b"\n".join(blobs)
    pages = len(re.findall(rb"/Type\s*/Page(?![sA-Za-z])", joined))
    counts = [int(x) for x in re.findall(rb"/Type\s*/Pages[^>]*?/Count\s+(\d+)", joined)]
    declared = max(counts) if counts else None
    return {"pages": pages, "declared": declared,
            "agree": declared is None or declared == pages}


@dataclass
class SerialCensus:
    serial: str
    casefile_files: int = 0
    casefile_pages: int = 0
    srp_files: int = 0
    srp_pages: int = 0
    parts: dict = field(default_factory=dict)   # part_no -> pages

    @property
    def total_files(self) -> int:
        return self.casefile_files + self.srp_files

    @property
    def total_pages(self) -> int:
        return self.casefile_pages + self.srp_pages


def census(files: list[tuple[str, int]]) -> dict:
    """Build a serial -> census map from [(filename, pages), ...].

    SRPs are counted separately and never folded into casefile parts, so the
    casefile total and the broader total stay distinguishable.
    """
    out: dict[str, SerialCensus] = {}
    problems = []
    for name, pages in files:
        serial = parse_serial(name)
        if serial is None:
            problems.append({"file": name, "problem": "no serial parsed"})
            continue
        c = out.setdefault(serial, SerialCensus(serial))
        if is_srp(name):
            c.srp_files += 1
            c.srp_pages += pages
            continue
        c.casefile_files += 1
        c.casefile_pages += pages
        part, of = parse_part(name)
        if part is not None:
            if part in c.parts:
                problems.append({"file": name, "problem": f"duplicate Part {part} for {serial}"})
            c.parts[part] = pages

    for c in out.values():
        if c.parts:
            expected = set(range(1, max(c.parts) + 1))
            missing = sorted(expected - set(c.parts))
            if missing:
                problems.append({"serial": c.serial, "problem": f"missing Part(s) {missing}"})

    return {
        "by_serial": out,
        "casefile_files": sum(c.casefile_files for c in out.values()),
        "casefile_pages": sum(c.casefile_pages for c in out.values()),
        "srp_files": sum(c.srp_files for c in out.values()),
        "srp_pages": sum(c.srp_pages for c in out.values()),
        "total_files": sum(c.total_files for c in out.values()),
        "total_pages": sum(c.total_pages for c in out.values()),
        "problems": problems,
    }
