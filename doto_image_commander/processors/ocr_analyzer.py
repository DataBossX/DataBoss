"""OCR analysis pipeline: send page images to OpenAI and store structured results."""

import json
from pathlib import Path

from core.database import fetch_all, fetch_one, execute
from core.audit import record
from api.openai_client import analyzer
from processors.pdf_processor import get_page_images_for_download


def analyze_download(download_id: int, queue_item_id: int,
                     progress_cb=None) -> dict:
    """
    Run OpenAI analysis on all pages of a downloaded document.
    Stores result in analyses table. Returns result dict.
    """
    # Skip if already analyzed
    existing = fetch_one(
        "SELECT id FROM analyses WHERE download_id=?", (download_id,))
    if existing:
        return {"skipped": True, "analysis_id": existing["id"]}

    image_paths = get_page_images_for_download(download_id)
    if not image_paths:
        return {"skipped": True, "reason": "No page images found"}

    # Filter to existing files
    image_paths = [p for p in image_paths if Path(p).exists()]
    if not image_paths:
        return {"skipped": True, "reason": "Page image files missing on disk"}

    if progress_cb:
        progress_cb(f"Analyzing {len(image_paths)} page(s)...")

    result = analyzer.analyze_pages(image_paths, queue_item_id=queue_item_id)

    openai_cost = result.pop("_openai_cost", 0.0)
    raw_response = result.pop("_raw_response", "")

    def _safe_json(v):
        if isinstance(v, (list, dict)):
            return json.dumps(v)
        return str(v) if v is not None else None

    analysis_id = execute(
        """INSERT INTO analyses (
            download_id, queue_item_id, instrument_type, instrument_number,
            book, page, recording_date, instrument_date,
            grantors, grantees, legal_description, section, township, range_val,
            interest_conveyed, lease_royalty_terms, title_requirement_affected,
            confidence_score, openai_cost, needs_review, raw_response
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            download_id, queue_item_id,
            result.get("instrument_type"),
            result.get("instrument_number"),
            result.get("book"),
            result.get("page"),
            result.get("recording_date"),
            result.get("instrument_date"),
            _safe_json(result.get("grantors")),
            _safe_json(result.get("grantees")),
            result.get("legal_description"),
            result.get("section"),
            result.get("township"),
            result.get("range") or result.get("range_val"),
            result.get("interest_conveyed"),
            result.get("lease_royalty_terms"),
            result.get("title_requirement_affected"),
            result.get("confidence_score", 0.0),
            openai_cost,
            1 if result.get("needs_review") else 0,
            raw_response[:10000],  # cap stored response size
        ),
    )

    execute("UPDATE image_queue SET status='analyzed' WHERE id=?", (queue_item_id,))

    record("analysis_complete",
           f"download_id={download_id}, confidence={result.get('confidence_score', 0):.2f}",
           data={"analysis_id": analysis_id, "needs_review": result.get("needs_review")},
           api_called="openai", cost=openai_cost)

    return {
        "skipped": False,
        "analysis_id": analysis_id,
        "confidence_score": result.get("confidence_score", 0.0),
        "needs_review": bool(result.get("needs_review")),
        "openai_cost": openai_cost,
        "extracted": result,
    }


def run_analysis_batch(progress_cb=None) -> dict:
    """Analyze all downloaded-but-not-yet-analyzed documents."""
    # Get downloads with status=success that have no analysis
    downloads = fetch_all("""
        SELECT d.id AS download_id, d.queue_item_id
        FROM downloads d
        LEFT JOIN analyses a ON a.download_id = d.id
        WHERE d.status = 'success' AND a.id IS NULL
    """)

    results = []
    for i, dl in enumerate(downloads):
        if progress_cb:
            progress_cb(f"Analyzing {i + 1}/{len(downloads)}...")
        r = analyze_download(dl["download_id"], dl["queue_item_id"], progress_cb)
        results.append(r)

    return {
        "total": len(downloads),
        "analyzed": sum(1 for r in results if not r.get("skipped")),
        "skipped": sum(1 for r in results if r.get("skipped")),
        "needs_review": sum(1 for r in results if r.get("needs_review")),
    }
