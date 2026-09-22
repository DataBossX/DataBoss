"""Synthetic PDFs and packets for tests. Never used as client evidence."""

from __future__ import annotations

from pathlib import Path


def write_minimal_pdf(path: str | Path, pages: int = 1) -> Path:
    """Write a tiny PDF with ``pages`` /Type /Page objects and a matching Count."""
    if pages < 1:
        raise ValueError("pages must be >= 1")
    destination = Path(path)
    kids = " ".join(f"{3 + index} 0 R" for index in range(pages))
    objects = [
        "%PDF-1.1",
        "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj",
        f"2 0 obj<</Type/Pages/Kids[{kids}]/Count {pages}>>endobj",
    ]
    for index in range(pages):
        number = 3 + index
        objects.append(
            f"{number} 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj"
        )
    joined = "\n".join(objects) + "\n"
    encoded = joined.encode("latin-1")
    positions: list[int] = []
    search_from = 0
    for number in range(1, pages + 3):
        token = f"{number} 0 obj".encode("ascii")
        pos = encoded.find(token, search_from)
        positions.append(pos)
        search_from = pos + 1
    xref_lines = ["xref", f"0 {pages + 3}", "0000000000 65535 f "]
    for pos in positions:
        xref_lines.append(f"{pos:010d} 00000 n ")
    xref = "\n".join(xref_lines) + "\n"
    trailer = (
        f"trailer<</Size {pages + 3}/Root 1 0 R>>\nstartxref\n{len(joined)}\n%%EOF\n"
    )
    destination.write_bytes(encoded + (xref + trailer).encode("latin-1"))
    return destination


def clean_row(**overrides: object) -> dict:
    row = {
        "Document Type": "Oil and Gas Lease",
        "Grantor": "Jane Example",
        "Grantee": "Example Minerals LLP",
        "Page": "1",
        "Date of Doc": "1/15/1980",
        "Rec Date": "1/20/1980",
        "Legal Description": "NE/4 of fictional Section 99",
        "Comments": "",
    }
    row.update(overrides)
    return row
