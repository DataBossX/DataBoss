"""Count physical PDF pages from the object graph. Never guess."""

from __future__ import annotations

import re
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path

from .hashing import sha256_file

_PAGE_TYPE = re.compile(rb"/Type\s*/Page(?![sA-Za-z])")
_PAGES_COUNT = re.compile(rb"/Type\s*/Pages[^>]*?/Count\s+(\d+)")


@dataclass(frozen=True)
class PdfCensus:
    path: str
    sha256: str
    byte_size: int
    counted_pages: int | None
    declared_pages: int | None
    agree: bool
    issues: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _decompress_streams(data: bytes) -> list[bytes]:
    blobs = [data]
    cursor = 0
    while True:
        start = data.find(b"stream", cursor)
        if start == -1:
            break
        header_end = data.find(b"\n", start)
        if header_end == -1:
            break
        end = data.find(b"endstream", header_end)
        if end == -1:
            break
        payload = data[header_end + 1 : end]
        if payload.startswith(b"\r"):
            payload = payload[1:]
        try:
            blobs.append(zlib.decompress(payload))
        except zlib.error:
            pass
        cursor = end + 9
    return blobs


def count_pdf_pages(path: str | Path) -> PdfCensus:
    """Return a census. Disagreement is reported, never resolved by inference."""
    source = Path(path)
    issues: list[str] = []
    if not source.exists():
        return PdfCensus(
            path=str(source),
            sha256="",
            byte_size=0,
            counted_pages=None,
            declared_pages=None,
            agree=False,
            issues=("MISSING_SOURCE",),
        )
    data = source.read_bytes()
    if not data.startswith(b"%PDF"):
        return PdfCensus(
            path=str(source),
            sha256=sha256_file(source),
            byte_size=len(data),
            counted_pages=None,
            declared_pages=None,
            agree=False,
            issues=("NOT_A_PDF",),
        )
    joined = b"\n".join(_decompress_streams(data))
    counted = len(_PAGE_TYPE.findall(joined))
    declared_matches = [int(value) for value in _PAGES_COUNT.findall(joined)]
    declared = max(declared_matches) if declared_matches else None
    if counted == 0:
        issues.append("NO_PAGE_OBJECTS")
    if declared is None:
        issues.append("NO_DECLARED_COUNT")
    if declared is not None and declared != counted:
        issues.append("PAGE_COUNT_DISAGREES")
    agree = counted > 0 and (declared is None or declared == counted)
    return PdfCensus(
        path=str(source),
        sha256=sha256_file(source),
        byte_size=len(data),
        counted_pages=counted or None,
        declared_pages=declared,
        agree=agree,
        issues=tuple(issues),
    )
