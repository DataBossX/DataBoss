"""file_inventory -- inventory every local input file (hash, size, type, pages)."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from ..model import SourceFile


def _sha256(path: str, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _pdf_page_count(path: str) -> int | None:
    """Count PDF pages without external tools.

    Prefers the page-tree /Count value (accurate even for image-only PDFs),
    then falls back to counting /Type /Page objects.
    """
    import re
    import zlib

    def _count_pages(blob: bytes) -> int:
        counts = [int(m) for m in re.findall(rb"/Count\s+(\d+)", blob)]
        best = max(counts) if counts else 0
        pages = blob.count(b"/Type /Page") - blob.count(b"/Type /Pages")
        if pages <= 0:
            pages = blob.count(b"/Type/Page") - blob.count(b"/Type/Pages")
        return max(best, pages)

    try:
        data = Path(path).read_bytes()
        best = _count_pages(data)
        # Image-only PDFs keep the page tree inside FlateDecode object streams;
        # inflate them so the count is accurate, not an undercount.
        for m in re.finditer(rb"stream\r?\n", data):
            start = m.end()
            end = data.find(b"endstream", start)
            if end == -1:
                continue
            try:
                inflated = zlib.decompress(data[start:end])
                best = max(best, _count_pages(inflated))
            except Exception:
                continue
        return best if best > 0 else None
    except Exception:
        return None


def build_inventory(input_dir: str) -> list[SourceFile]:
    files: list[SourceFile] = []
    for entry in sorted(os.listdir(input_dir)):
        full = os.path.join(input_dir, entry)
        if not os.path.isfile(full):
            continue
        ext = entry.lower().rsplit(".", 1)[-1] if "." in entry else ""
        kind = {"xlsx": "xlsx", "xls": "xlsx", "pdf": "pdf"}.get(ext, "other")
        pages = _pdf_page_count(full) if kind == "pdf" else None
        files.append(
            SourceFile(
                path=full,
                name=entry,
                kind=kind,
                size_bytes=os.path.getsize(full),
                sha256=_sha256(full),
                pages=pages,
                note="logged source-of-record",
            )
        )
    return files
