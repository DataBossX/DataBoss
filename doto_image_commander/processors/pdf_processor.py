"""PDF download orchestration and page-image extraction using PyMuPDF."""

import re
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image

from core.config import config, ensure_dirs
from core.database import fetch_all, fetch_one, execute
from core.audit import record
from api.okcounty import client as ok_client


def _safe_filename(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-.]", "_", str(text).strip())


def _pdf_dest_path(item: dict) -> Path:
    county = _safe_filename(item.get("county", "unknown"))
    itype = _safe_filename(item.get("instrument_type", "unknown"))
    book = _safe_filename(item.get("book", ""))
    page = _safe_filename(item.get("page", ""))
    inst = _safe_filename(item.get("instrument_number", item.get("image_number", str(item["id"]))))

    folder = config.DOWNLOADS_DIR / county / itype / f"Book{book}_Page{page}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{inst}.pdf"


def _images_dir(item: dict) -> Path:
    county = _safe_filename(item.get("county", "unknown"))
    itype = _safe_filename(item.get("instrument_type", "unknown"))
    book = _safe_filename(item.get("book", ""))
    page = _safe_filename(item.get("page", ""))
    inst = _safe_filename(item.get("instrument_number", item.get("image_number", str(item["id"]))))
    folder = config.IMAGES_DIR / county / itype / f"Book{book}_Page{page}" / inst
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def pdf_to_page_images(pdf_path: str, out_dir: Path, dpi: int = 200) -> list[str]:
    """Convert each PDF page to a JPEG and return list of image paths."""
    doc = fitz.open(pdf_path)
    paths = []
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        img_path = out_dir / f"page_{i + 1:03d}.jpg"
        pix.save(str(img_path))
        paths.append(str(img_path))
    doc.close()
    return paths


def download_approved_item(queue_item: dict,
                           progress_cb=None) -> dict:
    """
    Download one approved queue item:
      1. Search API for document URL
      2. Download PDF
      3. Convert to page images
      4. Record in DB
    Returns result dict.
    """
    ensure_dirs()
    item_id = queue_item["id"]
    dest_pdf = _pdf_dest_path(queue_item)
    img_dir = _images_dir(queue_item)

    if progress_cb:
        progress_cb(f"Searching for {queue_item.get('instrument_number', '')}...")

    # Mark as downloading
    execute("UPDATE image_queue SET status='downloading' WHERE id=?", (item_id,))

    # Create downloads record
    dl_id = execute(
        "INSERT INTO downloads (queue_item_id, file_path, status) VALUES (?,?,?)",
        (item_id, str(dest_pdf), "downloading"),
    )

    try:
        search_result = ok_client.search_document(
            county=queue_item.get("county", ""),
            book=queue_item.get("book"),
            page=queue_item.get("page"),
            instrument_number=queue_item.get("instrument_number"),
            image_number=queue_item.get("image_number"),
            instrument_type=queue_item.get("instrument_type"),
        )

        if not search_result:
            raise ValueError("Document not found in OKCountyRecords API")

        if progress_cb:
            progress_cb(f"Downloading PDF...")

        if search_result.download_url:
            dl_result = ok_client.download_by_url(
                search_result.download_url, str(dest_pdf), queue_item_id=item_id)
        else:
            dl_result = ok_client.download_document(
                search_result.document_id, str(dest_pdf), queue_item_id=item_id)

        if not dl_result.success:
            raise RuntimeError(dl_result.error or "Download failed")

        if progress_cb:
            progress_cb("Converting PDF to images...")

        image_paths = pdf_to_page_images(str(dest_pdf), img_dir)

        # Store page records
        for idx, img_path in enumerate(image_paths):
            execute(
                "INSERT INTO document_pages (download_id, page_number, image_path) VALUES (?,?,?)",
                (dl_id, idx + 1, img_path),
            )

        execute(
            "UPDATE downloads SET status='success', file_size_bytes=?, api_charge=?, downloaded_at=datetime('now') WHERE id=?",
            (dl_result.file_size_bytes, dl_result.actual_charge, dl_id),
        )
        execute("UPDATE image_queue SET status='downloaded' WHERE id=?", (item_id,))

        return {
            "success": True,
            "queue_item_id": item_id,
            "download_id": dl_id,
            "pdf_path": str(dest_pdf),
            "page_images": image_paths,
            "charge": dl_result.actual_charge,
        }

    except Exception as e:
        execute(
            "UPDATE downloads SET status='failed', error_message=? WHERE id=?",
            (str(e), dl_id),
        )
        execute("UPDATE image_queue SET status='failed' WHERE id=?", (item_id,))
        record("download_error", f"Queue item {item_id} failed: {e}")
        return {
            "success": False,
            "queue_item_id": item_id,
            "download_id": dl_id,
            "error": str(e),
            "charge": 0.0,
        }


def get_page_images_for_download(download_id: int) -> list[str]:
    rows = fetch_all(
        "SELECT image_path FROM document_pages WHERE download_id=? ORDER BY page_number",
        (download_id,),
    )
    return [r["image_path"] for r in rows]
