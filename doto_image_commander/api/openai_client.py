"""OpenAI vision API client for document OCR and structured extraction."""

import base64
import json
import os
from pathlib import Path
from typing import Optional

from openai import OpenAI

from core.config import config
from core.audit import record
from core.database import track_cost

EXTRACTION_PROMPT = """You are an expert Oklahoma land title examiner analyzing a scanned county land record document.

Extract ALL of the following fields from this document image. For each field, extract exactly what the document says.
If a field is not present or not readable, use null.

Return ONLY valid JSON with these exact keys:
{
  "instrument_type": "string - e.g. Warranty Deed, Oil and Gas Lease, Quit Claim Deed, Assignment, Release, Mortgage, Affidavit, Mineral Deed, Plat, Easement, Judgment, Lien, Decree",
  "instrument_number": "string - the clerk-assigned instrument/document number",
  "book": "string - record book number",
  "page": "string - record page number",
  "recording_date": "string - date filed/recorded with clerk (YYYY-MM-DD preferred)",
  "instrument_date": "string - date the instrument was executed/signed (YYYY-MM-DD preferred)",
  "grantors": ["array of grantor names - sellers, lessors, mortgagors"],
  "grantees": ["array of grantee names - buyers, lessees, mortgagees"],
  "legal_description": "string - full legal description of the property",
  "section": "string - section number (1-36)",
  "township": "string - township (e.g. 14N)",
  "range": "string - range (e.g. 7W)",
  "county": "string - Oklahoma county name",
  "interest_conveyed": "string - describe the interest: fee simple, mineral interest, royalty interest, working interest, surface only, etc.",
  "lease_royalty_terms": "string - for leases: royalty fraction, primary term, delay rental, etc. null for non-leases",
  "title_requirement_affected": "string - which title requirement this instrument satisfies or affects, if discernible",
  "notes": "string - any unusual clauses, exceptions, reservations, or items needing human review",
  "confidence_score": 0.0,
  "needs_review": false
}

Set confidence_score between 0.0 and 1.0 based on image clarity and your certainty.
Set needs_review to true if the image is unclear, the document is unusual, or if any critical field could not be read.
"""


class OpenAIDocumentAnalyzer:
    def __init__(self):
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY not configured.")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def is_configured(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY", ""))

    def reload_key(self) -> None:
        self._client = None

    @staticmethod
    def _image_to_b64(image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    def analyze_pages(self, image_paths: list[str],
                      queue_item_id: int = None) -> dict:
        """Send one or more page images to OpenAI and extract structured data."""
        client = self._get_client()

        content = [{"type": "text", "text": EXTRACTION_PROMPT}]
        for p in image_paths[:5]:  # cap at 5 pages per call to manage tokens/cost
            b64 = self._image_to_b64(p)
            suffix = Path(p).suffix.lower()
            mime = "image/png" if suffix == ".png" else "image/jpeg"
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
            })

        record("openai_analyze_start", f"Analyzing {len(image_paths)} page(s)",
               api_called="openai/chat.completions")

        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[{"role": "user", "content": content}],
            max_tokens=config.OPENAI_MAX_TOKENS,
            response_format={"type": "json_object"},
        )

        usage = response.usage
        # Approximate cost: $2.50/1M input, $10/1M output for gpt-4o (May 2025 pricing)
        cost = (usage.prompt_tokens * 2.50 + usage.completion_tokens * 10.0) / 1_000_000
        track_cost("openai", cost,
                   f"Analysis: {len(image_paths)} pages", queue_item_id=queue_item_id)
        record("openai_analyze_done",
               f"Tokens: {usage.prompt_tokens}+{usage.completion_tokens}, cost ~${cost:.4f}",
               api_called="openai/chat.completions", cost=cost)

        raw_text = response.choices[0].message.content
        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            result = {"raw_text": raw_text, "confidence_score": 0.0, "needs_review": True}

        result["_openai_cost"] = cost
        result["_raw_response"] = raw_text
        return result


analyzer = OpenAIDocumentAnalyzer()
