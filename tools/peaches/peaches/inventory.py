"""Inventory a directory tree: hashes, sizes, PDF page counts.

CLI: python -m peaches.inventory <root> <outdir>
Writes <outdir>/inventory.csv and <outdir>/inventory.json.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

try:
    import pymupdf as _pdf
except ImportError:  # older PyMuPDF
    import fitz as _pdf


def sha256_file(path, chunk=1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def pdf_info(path):
    """Return (pages, native_text_pages, error)."""
    try:
        doc = _pdf.open(path)
        try:
            pages = doc.page_count
            text_pages = 0
            for i in range(pages):
                if doc[i].get_text().strip():
                    text_pages += 1
            return pages, text_pages, ""
        finally:
            doc.close()
    except Exception as exc:  # unreadable PDF: record, never guess
        return None, None, "%s: %s" % (type(exc).__name__, exc)


def run_inventory(root, outdir):
    root = os.path.abspath(root)
    os.makedirs(outdir, exist_ok=True)
    rows = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            ext = os.path.splitext(name)[1].lower()
            if ext not in (".pdf", ".ods", ".xlsx"):
                continue
            row = {
                "path": rel,
                "name": name,
                "ext": ext,
                "bytes": os.path.getsize(path),
                "sha256": sha256_file(path),
                "pages": "",
                "native_text_pages": "",
                "error": "",
            }
            if ext == ".pdf":
                pages, text_pages, err = pdf_info(path)
                row["pages"] = "" if pages is None else pages
                row["native_text_pages"] = "" if text_pages is None else text_pages
                row["error"] = err
            rows.append(row)
    csv_path = os.path.join(outdir, "inventory.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "path", "name", "ext", "bytes", "sha256", "pages",
            "native_text_pages", "error"])
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "root": root,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "file_count": len(rows),
        "pdf_count": sum(1 for r in rows if r["ext"] == ".pdf"),
        "workbook_count": sum(1 for r in rows if r["ext"] in (".ods", ".xlsx")),
        "pdf_pages_total": sum(r["pages"] for r in rows if isinstance(r["pages"], int)),
        "files": rows,
    }
    with open(os.path.join(outdir, "inventory.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return summary


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: python -m peaches.inventory <root> <outdir>", file=sys.stderr)
        return 2
    summary = run_inventory(argv[0], argv[1])
    print("inventory: %d files (%d PDFs, %d workbooks), %d PDF pages -> %s"
          % (summary["file_count"], summary["pdf_count"],
             summary["workbook_count"], summary["pdf_pages_total"], argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
