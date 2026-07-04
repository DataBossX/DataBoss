"""Open a county-record document in the user's browser, capture evidence.

Captures (whatever is lawfully available in the user's session):
  * page text
  * a full-page screenshot
  * a downloaded PDF/image when the site offers it and the user is entitled

Then hands the captured images to the vision model for extraction. On CAPTCHA,
login, payment token, or a broken viewer, it PAUSES and asks the human to take
over the visible window — it never tries to bypass anything.
"""
from __future__ import annotations

import time
from pathlib import Path

from .. import config
from ..db import store
from ..models import registry
from ..schemas import DocExtraction
from ..runsheet.doctypes import normalize

# Heuristics that mean "stop and let the human drive".
TAKEOVER_MARKERS = (
    "captcha", "verify you are human", "sign in", "log in", "subscribe",
    "payment", "purchase", "add to cart", "session expired",
)

DOC_INSTRUCTION = f"""You are an Oklahoma title examiner reading a recorded
instrument image for Section {config.TARGET_SECTION}-{config.TARGET_TOWNSHIP}-{config.TARGET_RANGE},
{config.TARGET_COUNTY} County. Extract ONLY what the document states. Use null
for anything absent or unreadable. Do not compute net acres unless the document
explicitly states the fraction/decimal.

Return ONLY JSON:
{{
 "instrument_number": null, "book_page": null,
 "doc_type_original": null,
 "effective_date": null, "recorded_date": null,
 "grantor": null, "grantee": null,
 "legal_description": null,
 "section": null, "township": null, "range": null,
 "tracts": null,
 "classification": null,   // Mineral|Leasehold|Surface|Royalty|Other
 "conveyance_type": null,
 "conveyance_amount_dec": null,
 "gross_acres": null,
 "net_acres": null,
 "royalty": null, "primary_term": null,
 "recording_references": null,
 "notes": null,
 "confidence": 0.0
}}"""


def needs_takeover(page_text: str) -> bool:
    low = (page_text or "").lower()
    return any(m in low for m in TAKEOVER_MARKERS)


def capture_document(session, url: str, queue_id: int,
                     evidence_dir: Path = config.EVIDENCE_DIR) -> dict:
    """Navigate to url in the user's browser and capture evidence. Returns a
    dict with keys: page_text, screenshot, takeover (bool)."""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    page = session.new_page()
    out = {"url": url, "takeover": False}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        time.sleep(1.0)
        text = page.inner_text("body") if page.query_selector("body") else ""
        out["page_text"] = text
        shot = evidence_dir / f"q{queue_id}_screenshot.png"
        page.screenshot(path=str(shot), full_page=True)
        out["screenshot"] = str(shot)

        store.add_evidence(queue_id, "page_text", source_url=url,
                           payload={"text": text[:20000]})
        store.add_evidence(queue_id, "screenshot", source_url=url, file_path=str(shot))

        if needs_takeover(text):
            out["takeover"] = True
            store.audit("manual_takeover_required", url, {"queue_id": queue_id})
    finally:
        # Close the tab after capturing to avoid leaking a tab per document on
        # long batch runs. If takeover is needed, leave it open for the human.
        if not out.get("takeover"):
            try:
                page.close()
            except Exception:
                pass
    return out


def extract_from_images(image_paths: list[str], queue_id: int,
                        source_url: str | None = None) -> DocExtraction:
    raw = registry.extract_json(image_paths, DOC_INSTRUCTION)
    provider = raw.get("_provider")
    canon, original = normalize(raw.get("doc_type_original"))
    conf = float(raw.get("confidence", 0.0) or 0.0)

    review_flags, need_flags = [], []
    if conf < config.CONFIDENCE_REVIEW_THRESHOLD:
        review_flags.append("VERIFY: OCR uncertain")
    if canon is None and original:
        # Unrecognized doc type -> always flag for human review, not only leases.
        if "lease" in original.lower():
            need_flags.append("NEED: review lease terms")
        else:
            review_flags.append("VERIFY: OCR uncertain")

    ext = DocExtraction(
        instrument_number=raw.get("instrument_number"),
        book_page=raw.get("book_page"),
        doc_type=canon,
        doc_type_original=original,
        effective_date=raw.get("effective_date"),
        recorded_date=raw.get("recorded_date"),
        grantor=raw.get("grantor"),
        grantee=raw.get("grantee"),
        legal_description=raw.get("legal_description"),
        section=raw.get("section"),
        township=raw.get("township"),
        range=raw.get("range"),
        tracts=raw.get("tracts"),
        classification=raw.get("classification") if raw.get("classification") in
        ("Mineral", "Leasehold", "Surface", "Royalty", "Other") else None,
        conveyance_type=raw.get("conveyance_type"),
        conveyance_amount_dec=raw.get("conveyance_amount_dec"),
        gross_acres=raw.get("gross_acres"),
        net_acres=raw.get("net_acres"),
        royalty=raw.get("royalty"),
        primary_term=raw.get("primary_term"),
        recording_references=raw.get("recording_references"),
        document_link=source_url,
        notes=raw.get("notes"),
        review_flags=[f for f in review_flags if f],
        need_flags=[f for f in need_flags if f],
        confidence=conf,
        needs_review=conf < config.CONFIDENCE_REVIEW_THRESHOLD,
    )
    store.add_evidence(queue_id, "extraction", provider=provider,
                       source_url=source_url, confidence=conf,
                       payload=ext.model_dump(by_alias=True))
    return ext
