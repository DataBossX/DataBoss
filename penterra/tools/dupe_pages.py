"""Duplicate-page SHA detection across a source corpus."""
from __future__ import annotations

import hashlib
from collections import defaultdict


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def find_duplicate_pages(pages: list[tuple[str, int, bytes]]) -> dict:
    """pages = [(file, page_no, page_bytes)]. Group identical rendered pages.

    A duplicate page across two different source files usually means the same
    instrument was scanned twice; it must be dispositioned, not abstracted
    twice. Repeated pages *inside* one file are reported separately because
    those are usually legitimate (blank separators, repeated exhibits).
    """
    by_digest = defaultdict(list)
    for f, p, b in pages:
        by_digest[sha256_bytes(b)].append((f, p))

    cross, intra = [], []
    for digest, locs in by_digest.items():
        if len(locs) < 2:
            continue
        files = {f for f, _ in locs}
        rec = {"sha256": digest, "occurrences": sorted(locs), "count": len(locs)}
        (cross if len(files) > 1 else intra).append(rec)

    return {"cross_file_duplicates": sorted(cross, key=lambda r: -r["count"]),
            "intra_file_duplicates": sorted(intra, key=lambda r: -r["count"]),
            "unique_pages": len(by_digest), "total_pages": len(pages)}
