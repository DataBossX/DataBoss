"""Count every image once. A PDF is a container; each page is one image."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".gif", ".webp", ".bmp"}
PDF_EXTENSIONS = {".pdf"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def is_pdf(path: Path) -> bool:
    if path.suffix.lower() in PDF_EXTENSIONS:
        return True
    with path.open("rb") as handle:
        return handle.read(5).startswith(b"%PDF-")


def pdf_page_count(path: Path) -> int:
    import pymupdf

    document = pymupdf.open(path)
    try:
        return int(document.page_count)
    finally:
        document.close()


def account_path(path: Path) -> list[dict[str, object]]:
    """Return one ledger row per image. PDF containers add page rows only."""
    path = Path(path)
    if not path.is_file():
        return []
    file_sha = sha256_file(path)
    if is_image(path):
        return [
            {
                "path": str(path),
                "kind": "raster",
                "sha256": file_sha,
                "bytes": path.stat().st_size,
                "page": 1,
                "images": 1,
            }
        ]
    if is_pdf(path):
        pages = pdf_page_count(path)
        return [
            {
                "path": str(path),
                "kind": "pdf_page",
                "sha256": file_sha,
                "bytes": path.stat().st_size,
                "page": page,
                "images": 1,
            }
            for page in range(1, pages + 1)
        ]
    return [
        {
            "path": str(path),
            "kind": "non_image",
            "sha256": file_sha,
            "bytes": path.stat().st_size,
            "page": None,
            "images": 0,
        }
    ]


def account_paths(paths: Iterable[Path]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for path in paths:
        rows.extend(account_path(Path(path)))
    image_rows = [row for row in rows if int(row["images"]) > 0]
    return {
        "every_image_accounted": bool(image_rows) and all(row.get("sha256") for row in image_rows),
        "image_count": sum(int(row["images"]) for row in rows),
        "file_count": len({row["path"] for row in rows}),
        "pdf_container_extra_images": 0,
        "rows": rows,
    }
