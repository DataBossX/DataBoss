"""Locate and score prior title reports for improvement.

Searches DataBossX report/workbook/document trees plus configured extras. Scores
each candidate on relevance, recency, completeness, source references, and
coverage of tract/OGL/WI/chain topics. Never overwrites a found report.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from config.settings import Settings

_REPORT_EXTS = {".md", ".pdf", ".docx", ".xlsx", ".csv", ".txt"}
_TOPIC_TERMS = ("tract", "ogl", "working interest", "chain", "grantor", "grantee",
                "instrument", "book", "page", "hbp", "certification", "escalation",
                "runsheet", "acreage")


@dataclass
class ReportCandidate:
    path: Path
    score: float
    mtime: float
    size: int
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "score": round(self.score, 3),
            "mtime": self.mtime,
            "size": self.size,
            "reasons": self.reasons,
        }


class ReportFinder:
    def __init__(self, settings: Settings, extra_dirs: Optional[List[Path]] = None) -> None:
        self.settings = settings
        self.extra_dirs = extra_dirs or []

    def _dirs(self) -> List[Path]:
        base = self.settings.databossx_root
        dirs = [
            base,
            self.settings.outputs_dir,
            base / "reports",
            base / "workbooks",
            base / "documents",
        ]
        dirs.extend(self.settings.extra_source_dirs)
        dirs.extend(self.extra_dirs)
        return [d for d in dirs if d.exists() and d.is_dir()]

    def _score(self, path: Path, workbook_stem: Optional[str]) -> ReportCandidate:
        reasons: List[str] = []
        score = 0.0
        try:
            stat = path.stat()
        except OSError:
            return ReportCandidate(path, 0.0, 0.0, 0, ["unreadable"])
        name = path.name.lower()

        # relevance to workbook/prospect
        if workbook_stem and workbook_stem.lower() in name:
            score += 5.0
            reasons.append("filename matches workbook")

        # text-content topic coverage for text-like formats
        text = ""
        if path.suffix.lower() in {".md", ".txt", ".csv"}:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                text = ""
        haystack = f"{name} {text}"
        covered = [t for t in _TOPIC_TERMS if t in haystack]
        score += len(covered) * 0.5
        if covered:
            reasons.append(f"covers: {', '.join(covered[:6])}")

        # source references
        if re.search(r"book\s*\d+|instrument\s*\d+|page\s*\d+", haystack):
            score += 1.5
            reasons.append("contains source references")

        # certification / escalation status
        if "certif" in haystack:
            score += 1.0
            reasons.append("mentions certification")
        if "escalat" in haystack:
            score += 0.5
            reasons.append("mentions escalation")

        # completeness proxy: size
        if stat.st_size > 2000:
            score += 0.5

        # recency (normalized, small weight)
        score += min(stat.st_mtime / 1e12, 0.5)

        return ReportCandidate(
            path=path, score=score, mtime=stat.st_mtime, size=stat.st_size, reasons=reasons
        )

    def find(self, workbook_stem: Optional[str] = None, limit: int = 20) -> List[ReportCandidate]:
        candidates: List[ReportCandidate] = []
        for d in self._dirs():
            for path in d.rglob("*"):
                if path.is_file() and path.suffix.lower() in _REPORT_EXTS:
                    candidates.append(self._score(path, workbook_stem))
        candidates.sort(key=lambda c: (c.score, c.mtime), reverse=True)
        return candidates[:limit]

    def best(self, workbook_stem: Optional[str] = None) -> Optional[ReportCandidate]:
        found = self.find(workbook_stem, limit=1)
        return found[0] if found and found[0].score > 0 else None
