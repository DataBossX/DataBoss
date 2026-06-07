"""Shared helpers: logging, hashing, date normalization, confidence buckets."""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

LOG = logging.getLogger("title_report_factory")

# ----------------------------------------------------------------------------
# Sentinel values used instead of leaving important cells blank.
# ----------------------------------------------------------------------------
UNKNOWN = "Unknown"
NOT_FOUND = "Not Found"
NOT_APPLICABLE = "Not Applicable"
NEEDS_REVIEW = "Needs Review"


def configure_logging(verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    if not LOG.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s")
        )
        LOG.addHandler(handler)
    LOG.setLevel(level)
    return LOG


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    """Stable content hash, used to deduplicate documents."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", "ignore")).hexdigest()


# ----------------------------------------------------------------------------
# Date parsing -> always emit M/D/YYYY short dates for the workbook.
# ----------------------------------------------------------------------------
_DATE_PATTERNS = [
    "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y",
    "%Y-%m-%d", "%Y/%m/%d", "%B %d, %Y", "%b %d, %Y",
    "%d %B %Y", "%d %b %Y", "%m/%d/%Y %H:%M:%S",
]


def parse_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text in (UNKNOWN, NOT_FOUND, NOT_APPLICABLE, NEEDS_REVIEW):
        return None
    for fmt in _DATE_PATTERNS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    # Last resort: pull an embedded date.
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
    if m:
        mo, da, yr = m.groups()
        yr = int(yr)
        if yr < 100:
            yr += 2000 if yr < 50 else 1900
        try:
            return date(yr, int(mo), int(da))
        except ValueError:
            return None
    return None


def short_date(value) -> str:
    """Return an M/D/YYYY string, or a sentinel when the date is unknown."""
    d = parse_date(value)
    if d is None:
        return UNKNOWN if value in (None, "") else NEEDS_REVIEW
    return f"{d.month}/{d.day}/{d.year}"


def confidence_band(score: Optional[float]) -> str:
    if score is None:
        return UNKNOWN
    s = float(score)
    if s >= 90:
        return "Strong, clear, source-backed"
    if s >= 70:
        return "Good, minor uncertainty"
    if s >= 50:
        return "Usable but needs review"
    if s >= 25:
        return "Weak or incomplete"
    return "Unreliable or speculative"


def clamp_score(score: Optional[float]) -> Optional[int]:
    if score is None:
        return None
    return int(max(0, min(100, round(float(score)))))


def clean_ws(text: Optional[str]) -> str:
    return re.sub(r"[ \t]+", " ", (text or "")).strip()


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "file"
