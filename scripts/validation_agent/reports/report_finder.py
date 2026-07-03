"""Report finder.

Searches known DataBossX locations (and config-defined extras) for candidate
report files and scores them for recency, completeness, relevance, source
references, section coverage, and integrity. Never overwrites found reports.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPORT_EXTS = {".md", ".pdf", ".docx", ".xlsx", ".csv", ".txt"}

_SECTION_KEYWORDS = ["tract", "ogl", "working interest", "chain", "runsheet",
                     "escalation", "certification", "source", "book/page",
                     "instrument", "validation", "scorecard"]
_CITATION_KEYWORDS = ["bk ", "book ", "instrument", "inst.", "recorded",
                      "county clerk", "citation"]


@dataclass
class ReportCandidate:
    path: Path
    ext: str
    size_bytes: int
    mtime: float
    score: float = 0.0
    signals: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "ext": self.ext,
            "size_bytes": self.size_bytes,
            "mtime": self.mtime,
            "score": round(self.score, 2),
            "signals": self.signals,
        }


def _read_text_preview(path: Path, limit: int = 200_000) -> str:
    try:
        if path.suffix.lower() in {".md", ".txt", ".csv"}:
            return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        return ""
    return ""


class ReportFinder:
    def __init__(self, settings, workbook_stem: str = ""):
        self.settings = settings
        self.workbook_stem = (workbook_stem or "").lower()

    def _search_dirs(self) -> list[Path]:
        root = self.settings.project_root
        dirs = [
            root,
            self.settings.outputs_dir,
            root / "reports",
            root / "workbooks",
            root / "documents",
        ]
        dirs.extend(self.settings.extra_report_dirs)
        seen: set[Path] = set()
        out: list[Path] = []
        for d in dirs:
            if d.exists() and d not in seen:
                seen.add(d)
                out.append(d)
        return out

    def find(self, max_depth: int = 4) -> list[ReportCandidate]:
        candidates: list[ReportCandidate] = []
        seen_files: set[Path] = set()
        for base in self._search_dirs():
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in _REPORT_EXTS:
                    continue
                # Bound recursion depth relative to base.
                try:
                    rel_parts = path.relative_to(base).parts
                except ValueError:
                    continue
                if len(rel_parts) > max_depth:
                    continue
                if path in seen_files:
                    continue
                seen_files.add(path)
                try:
                    st = path.stat()
                except OSError:
                    continue
                cand = ReportCandidate(
                    path=path, ext=path.suffix.lower(),
                    size_bytes=st.st_size, mtime=st.st_mtime,
                )
                self._score(cand)
                candidates.append(cand)
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def _score(self, cand: ReportCandidate) -> None:
        score = 0.0
        signals: dict[str, Any] = {}

        # Recency (newer is better) — normalized-ish contribution.
        signals["recency_rank"] = cand.mtime
        score += min(cand.mtime / 1e9, 2.0)

        # Completeness proxy: file size (with a cap).
        signals["size_score"] = min(cand.size_bytes / 5000.0, 20.0)
        score += signals["size_score"]

        # Preferred formats.
        fmt_bonus = {".md": 6, ".pdf": 5, ".docx": 5, ".xlsx": 3,
                     ".csv": 2, ".txt": 2}.get(cand.ext, 0)
        score += fmt_bonus
        signals["format_bonus"] = fmt_bonus

        text = _read_text_preview(cand.path).lower()
        if text:
            section_hits = [k for k in _SECTION_KEYWORDS if k in text]
            citation_hits = [k for k in _CITATION_KEYWORDS if k in text]
            signals["section_hits"] = section_hits
            signals["citation_hits"] = len(citation_hits)
            score += len(section_hits) * 2.0
            score += min(len(citation_hits), 10) * 1.5
            if "certified" in text or "certification" in text:
                score += 3.0
                signals["certification_ref"] = True
            if "escalat" in text:
                score += 1.5
                signals["escalation_ref"] = True

        # Relevance to current workbook.
        if self.workbook_stem and self.workbook_stem in cand.path.name.lower():
            score += 8.0
            signals["name_match"] = True

        cand.score = score
        cand.signals = signals

    def best(self) -> ReportCandidate | None:
        found = self.find()
        return found[0] if found else None
