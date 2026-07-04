"""
Report finder.

Searches configured roots for candidate reports (md/pdf/docx/xlsx/csv/txt),
scores them for recency/completeness/relevance/source-citations/section
coverage, and returns the best candidate. Never overwrites anything it finds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

REPORT_EXTS = {".md", ".pdf", ".docx", ".xlsx", ".csv", ".txt"}
RELEVANCE_TOKENS = ["cursory", "title", "tract", "ogl", "runsheet", "roger mills",
                    "31-12n-24w", "working interest", "curative", "ownership"]


@dataclass
class Candidate:
    path: str
    ext: str
    size: int
    mtime: float
    score: float = 0.0
    signals: List[str] = field(default_factory=list)


def _score(path: Path) -> Candidate:
    ext = path.suffix.lower()
    st = path.stat()
    c = Candidate(str(path), ext, st.st_size, st.st_mtime)
    score = 0.0
    sig = []
    name = path.name.lower()
    # relevance from filename
    for t in RELEVANCE_TOKENS:
        if t in name:
            score += 1.5
            sig.append(f"name:{t}")
    # text-readable formats let us look deeper
    if ext in {".md", ".txt", ".csv"}:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for t in RELEVANCE_TOKENS:
                if t in text:
                    score += 0.5
            for sect in ["tract", "ogl", "working interest", "chain", "curative", "source", "bk ", "/0"]:
                if sect in text:
                    score += 0.3
                    sig.append(f"sect:{sect.strip()}")
            if any(k in text for k in ["verified", "escalat", "certif"]):
                score += 0.5
                sig.append("status")
        except Exception:
            pass
    # completeness proxy: bigger structured files score a little higher
    score += min(st.st_size / 500_000.0, 3.0)
    # recency: newer files score higher (bounded)
    c.score = round(score, 3)
    c.signals = sig
    return c


class ReportFinder:
    def __init__(self, roots: List[str], extra_dirs: Optional[List[str]] = None):
        self.roots = [Path(r) for r in roots] + [Path(d) for d in (extra_dirs or [])]

    def find(self, limit: int = 50) -> List[Candidate]:
        seen = set()
        cands: List[Candidate] = []
        for root in self.roots:
            if not root.exists():
                continue
            for p in root.rglob("*"):
                if not p.is_file() or p.suffix.lower() not in REPORT_EXTS:
                    continue
                rp = str(p.resolve())
                if rp in seen:
                    continue
                seen.add(rp)
                try:
                    cands.append(_score(p))
                except Exception:
                    continue
        # sort by score desc then recency desc
        cands.sort(key=lambda c: (c.score, c.mtime), reverse=True)
        return cands[:limit]

    def best(self) -> Optional[Candidate]:
        c = self.find(limit=1)
        return c[0] if c else None
