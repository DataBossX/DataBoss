"""Report finder — locate and score candidate prior reports. Never overwrites."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

CANDIDATE_EXT = {".md", ".pdf", ".docx", ".xlsx", ".csv", ".txt"}
RELEVANCE_TOKENS = ["tract", "ogl", "working interest", "wi ", "chain", "hbp",
                    "book", "page", "instrument", "royalty", "source"]


def _score_text(text: str) -> Dict[str, Any]:
    t = text.lower()
    has_sources = bool(re.search(r"\b\d{3,4}\s*[/-]\s*\d{1,4}\b", t) or
                       re.search(r"\b\d{4}-\d{5,6}\b", t))
    relevance = sum(1 for tok in RELEVANCE_TOKENS if tok in t)
    sections = sum(1 for s in ["tract", "ogl", "working interest", "chain", "curative", "source"]
                   if s in t)
    return {"has_sources": has_sources, "relevance": relevance, "sections": sections,
            "length": len(text)}


def find_reports(search_dirs: List[Path], prospect_hint: str = "") -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    found: List[Dict[str, Any]] = []
    for d in search_dirs:
        d = Path(d)
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in CANDIDATE_EXT:
                continue
            try:
                stat = p.stat()
            except OSError:
                continue
            age_days = (now.timestamp() - stat.st_mtime) / 86400.0
            recency = max(0.0, 1.0 - min(age_days, 365) / 365.0)
            text = ""
            if p.suffix.lower() in {".md", ".txt", ".csv"} and stat.st_size < 2_000_000:
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    text = ""
            content = _score_text(text) if text else {"has_sources": False, "relevance": 0,
                                                       "sections": 0, "length": stat.st_size}
            name_relevance = sum(1 for tok in ["31-12n-24w", "roger mills", "ownership",
                                               "title", prospect_hint.lower()]
                                 if tok and tok in p.name.lower())
            score = (recency * 3 + content["relevance"] + content["sections"] * 2
                     + (2 if content["has_sources"] else 0) + name_relevance * 2)
            found.append({
                "path": str(p), "suffix": p.suffix.lower(), "size": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "score": round(score, 3), "has_sources": content["has_sources"],
                "relevance": content["relevance"], "sections": content["sections"]})
    found.sort(key=lambda r: r["score"], reverse=True)
    return found


def best_report(search_dirs: List[Path], prospect_hint: str = "") -> Optional[Dict[str, Any]]:
    reports = find_reports(search_dirs, prospect_hint)
    return reports[0] if reports else None
