"""
ai_extractors.py
================
Vision extraction + model router + consensus logic for HorizonTitleLinkExtractor.

Primary extractor : OpenAI vision model (OpenAI Responses API style).
Validator 1       : Gemini vision model   (only if GEMINI_API_KEY present).
Validator 2       : Claude vision model   (only if ANTHROPIC_API_KEY present).

The router only runs validators when warranted (low confidence, changed fields,
ambiguity, poor image quality, or config always_validate=true).

Hard rules enforced via the system prompt:
  * Read the actual document image, never guess from the spreadsheet row.
  * Preserve names, punctuation, initials, trustee language, company suffixes.
  * Do not over-normalize legal descriptions.
  * Return null for anything not visible. Never invent missing data.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

import image_utils
import matching
from cache import CostTracker, ResultCache, image_key

log = logging.getLogger("horizon.ai")

# Fields the consensus logic treats as "major" (drive validation + flagging).
MAJOR_FIELDS = [
    "instrument_number",
    "document_type",
    "book_page",
    "filed_date",
    "recorded_date",
    "effective_date",
    "grantor",
    "grantee",
    "legal_description",
    "section",
    "township",
    "range",
]


# -----------------------------------------------------------------------------
# Strict extraction schema
# -----------------------------------------------------------------------------
class TitleExtraction(BaseModel):
    instrument_number: str | None = None
    document_type: str | None = None
    book_page: str | None = None
    filed_date: str | None = None          # YYYY-MM-DD or null
    recorded_date: str | None = None       # YYYY-MM-DD or null
    effective_date: str | None = None      # YYYY-MM-DD or null
    grantor: str | None = None
    grantee: str | None = None
    legal_description: str | None = None
    section: str | None = None
    township: str | None = None
    range: str | None = None
    county: str | None = None
    state: str | None = None
    remarks: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertain_fields: list[str] = Field(default_factory=list)
    evidence_summary: str = ""
    needs_human_review: bool = False


# JSON Schema handed to providers that support structured output.
EXTRACTION_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "instrument_number": {"type": ["string", "null"]},
        "document_type": {"type": ["string", "null"]},
        "book_page": {"type": ["string", "null"]},
        "filed_date": {"type": ["string", "null"]},
        "recorded_date": {"type": ["string", "null"]},
        "effective_date": {"type": ["string", "null"]},
        "grantor": {"type": ["string", "null"]},
        "grantee": {"type": ["string", "null"]},
        "legal_description": {"type": ["string", "null"]},
        "section": {"type": ["string", "null"]},
        "township": {"type": ["string", "null"]},
        "range": {"type": ["string", "null"]},
        "county": {"type": ["string", "null"]},
        "state": {"type": ["string", "null"]},
        "remarks": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
        "uncertain_fields": {"type": "array", "items": {"type": "string"}},
        "evidence_summary": {"type": "string"},
        "needs_human_review": {"type": "boolean"},
    },
    "required": list({
        "instrument_number", "document_type", "book_page", "filed_date",
        "recorded_date", "effective_date", "grantor", "grantee",
        "legal_description", "section", "township", "range", "county",
        "state", "remarks", "confidence", "uncertain_fields",
        "evidence_summary", "needs_human_review",
    }),
}

SYSTEM_PROMPT = """You are a meticulous title/county-records examiner.
You are given an IMAGE of a recorded county document. Extract structured data.

ABSOLUTE RULES:
- Read ONLY the actual document image. Never guess from any spreadsheet or outside knowledge.
- Preserve names EXACTLY as written: punctuation, initials, "Jr."/"Sr.", trustee
  language, marital status, and company suffixes (LLC, Inc., L.P., Trust, et ux, et al).
- Preserve legal descriptions carefully. Do NOT over-normalize, reword, or "clean up".
- Preserve book/page formatting exactly as it appears.
- For dates, output YYYY-MM-DD ONLY when the date is clearly legible; otherwise null.
- Return null for any field that is not visible. NEVER invent missing data.
- If the image is blurry, cropped, blocked, sideways, or otherwise uncertain,
  set a LOW confidence value and list the affected fields in uncertain_fields.
- If multiple conflicting values appear, list the field in uncertain_fields and
  explain in evidence_summary.
- needs_human_review must be true whenever confidence is low or key fields are uncertain.

Return ONLY a JSON object that matches the provided schema. No prose outside JSON.
"""

USER_PROMPT = (
    "Extract the title document fields from this recorded county document image. "
    "Follow every rule. Output strict JSON only."
)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _b64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("ascii")


def _coerce(raw: dict[str, Any]) -> TitleExtraction:
    """Coerce a raw provider dict into a validated TitleExtraction."""
    try:
        return TitleExtraction(**raw)
    except ValidationError as exc:
        log.warning("Extraction failed schema validation, salvaging: %s", exc)
        safe = {k: raw.get(k) for k in TitleExtraction.model_fields if k in raw}
        safe.setdefault("confidence", 0.0)
        safe["needs_human_review"] = True
        try:
            return TitleExtraction(**safe)
        except ValidationError:
            return TitleExtraction(confidence=0.0, needs_human_review=True,
                                   evidence_summary="Unparseable model output.")


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a text blob."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model output.")
    return json.loads(text[start:end + 1])


# =============================================================================
# Model Router
# =============================================================================
class ModelRouter:
    """Routes a document image through primary + optional validator models and
    computes field-level consensus."""

    def __init__(self, config: dict[str, Any],
                 cost: CostTracker | None = None,
                 result_cache: ResultCache | None = None):
        self.config = config
        self.openai_model = config.get("openai_model", "gpt-5.2")
        self.gemini_model = config.get("gemini_model", "gemini-2.5-pro")
        self.claude_model = config.get("claude_model", "claude-sonnet-4")

        self.openai_key = os.getenv("OPENAI_API_KEY") or ""
        self.gemini_key = os.getenv("GEMINI_API_KEY") or ""
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY") or ""

        self.cost = cost or CostTracker()
        self.cache = result_cache or ResultCache(
            config.get("cache_dir", ".cache"),
            enabled=bool(config.get("use_cache", True)))
        self.agree_threshold = float(config.get("match_minor_threshold", 0.85))

        self._openai_client = None
        self._gemini_ready = False
        self._anthropic_client = None

    # --- lazy clients ------------------------------------------------------
    def _openai(self):
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI(api_key=self.openai_key)
        return self._openai_client

    def _gemini(self):
        if not self._gemini_ready:
            import google.generativeai as genai
            genai.configure(api_key=self.gemini_key)
            self._gemini_ready = True
        import google.generativeai as genai
        return genai

    def _anthropic(self):
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(api_key=self.anthropic_key)
        return self._anthropic_client

    # --- provider calls ----------------------------------------------------
    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=2, min=2, max=16), reraise=True)
    def run_openai(self, images: list[bytes]) -> tuple[TitleExtraction, int, int]:
        """Primary extractor using the OpenAI Responses API."""
        client = self._openai()
        content: list[dict[str, Any]] = [{"type": "input_text", "text": USER_PROMPT}]
        for img in images:
            content.append({
                "type": "input_image",
                "image_url": f"data:image/png;base64,{_b64(img)}",
            })
        resp = client.responses.create(
            model=self.openai_model,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
                {"role": "user", "content": content},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "title_extraction",
                    "schema": EXTRACTION_JSON_SCHEMA,
                    "strict": True,
                }
            },
        )
        text = getattr(resp, "output_text", None) or ""
        usage = getattr(resp, "usage", None)
        in_tok = getattr(usage, "input_tokens", 0) or 0
        out_tok = getattr(usage, "output_tokens", 0) or 0
        return _coerce(_extract_json(text)), in_tok, out_tok

    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=2, min=2, max=16), reraise=True)
    def run_gemini(self, images: list[bytes]) -> tuple[TitleExtraction, int, int]:
        genai = self._gemini()
        model = genai.GenerativeModel(
            self.gemini_model, system_instruction=SYSTEM_PROMPT)
        parts: list[Any] = [USER_PROMPT]
        for img in images:
            parts.append({"mime_type": "image/png", "data": img})
        resp = model.generate_content(
            parts, generation_config={"response_mime_type": "application/json"})
        um = getattr(resp, "usage_metadata", None)
        in_tok = getattr(um, "prompt_token_count", 0) or 0
        out_tok = getattr(um, "candidates_token_count", 0) or 0
        return _coerce(_extract_json(resp.text)), in_tok, out_tok

    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=2, min=2, max=16), reraise=True)
    def run_claude(self, images: list[bytes]) -> tuple[TitleExtraction, int, int]:
        client = self._anthropic()
        blocks: list[dict[str, Any]] = [{"type": "text", "text": USER_PROMPT}]
        for img in images:
            blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png",
                           "data": _b64(img)},
            })
        msg = client.messages.create(
            model=self.claude_model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": blocks}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        usage = getattr(msg, "usage", None)
        in_tok = getattr(usage, "input_tokens", 0) or 0
        out_tok = getattr(usage, "output_tokens", 0) or 0
        return _coerce(_extract_json(text)), in_tok, out_tok

    # --- routing -----------------------------------------------------------
    def _should_validate(self, primary: TitleExtraction,
                         poor_image: bool = False) -> bool:
        cfg = self.config
        if cfg.get("always_validate"):
            return True
        if poor_image:
            return True
        if primary.confidence < float(cfg.get("ai_confidence_review_threshold", 0.85)):
            return True
        if primary.needs_human_review:
            return True
        if primary.uncertain_fields:
            return True
        return False

    def extract(self, images: list[bytes], row_changed_hint: bool = False,
                row_id: Any = "") -> dict[str, Any]:
        """
        Run primary + (conditionally) validators, then compute consensus.

        Returns a dict:
          {
            "primary": TitleExtraction,
            "validators": {"gemini": TitleExtraction|None, "claude": TitleExtraction|None},
            "consensus": {field: value},
            "consensus_fields": [field, ...],   # fields where >=2 models agreed
            "disagree_fields": [field, ...],    # major fields with disagreement
            "models_used": str,
            "validator_models_used": [str, ...],
            "confidence": float,
            "needs_human_review": bool,
          }
        """
        # 1. Preprocess images for legibility + assess quality.
        if self.config.get("preprocess_images", True):
            prepared, quality = image_utils.prepare_for_ai(images)
        else:
            prepared, quality = images, None
        poor_image = bool(
            quality and quality.is_poor
            and self.config.get("flag_poor_image_quality", True))

        # 2. Primary extraction (cache by content hash to avoid repaid calls).
        pkey = image_key(self.openai_model, prepared)
        cached = self.cache.get(pkey)
        if cached is not None:
            primary = _coerce(cached)
            self.cost.record(self.openai_model, 0, 0, row=row_id, cached=True)
        else:
            primary, in_tok, out_tok = self.run_openai(prepared)
            self.cost.record(self.openai_model, in_tok, out_tok, row=row_id)
            self.cache.set(pkey, primary.model_dump())

        if poor_image:
            # A poor capture should never read as high confidence.
            primary.confidence = min(primary.confidence, 0.5)
            primary.needs_human_review = True

        models_used = self.openai_model
        validators: dict[str, TitleExtraction | None] = {"gemini": None, "claude": None}
        validator_models: list[str] = []

        run_validators = (self._should_validate(primary, poor_image)
                          or row_changed_hint)
        if run_validators:
            if self.gemini_key:
                try:
                    res, i, o = self.run_gemini(prepared)
                    validators["gemini"] = res
                    self.cost.record(self.gemini_model, i, o, row=row_id)
                    validator_models.append(self.gemini_model)
                except Exception as exc:  # continue after failures
                    log.warning("Gemini validator failed: %s", exc)
            if self.anthropic_key:
                try:
                    res, i, o = self.run_claude(prepared)
                    validators["claude"] = res
                    self.cost.record(self.claude_model, i, o, row=row_id)
                    validator_models.append(self.claude_model)
                except Exception as exc:
                    log.warning("Claude validator failed: %s", exc)

        consensus, consensus_fields, disagree_fields = self._consensus(
            primary, validators)

        needs_review = (
            primary.needs_human_review
            or bool(disagree_fields)
            or poor_image
            or primary.confidence < float(
                self.config.get("ai_confidence_review_threshold", 0.85))
        )

        return {
            "primary": primary,
            "validators": validators,
            "consensus": consensus,
            "consensus_fields": consensus_fields,
            "disagree_fields": disagree_fields,
            "models_used": models_used,
            "validator_models_used": validator_models,
            "confidence": primary.confidence,
            "needs_human_review": needs_review,
            "image_quality": quality.score if quality else None,
            "poor_image": poor_image,
        }

    # --- consensus ---------------------------------------------------------
    def _consensus(self, primary: TitleExtraction,
                   validators: dict[str, TitleExtraction | None]):
        """
        Per major field, using FIELD-AWARE FUZZY agreement (so "ACME L.L.C." and
        "ACME LLC" count as agreeing, but "NW/4" vs "NE/4" do not):
          * If >=2 of the available models agree, that value is the AI consensus.
          * If models disagree, the field is flagged for review and NO consensus
            value is produced (original cell stays untouched downstream).
          * Missing (null) values are never invented.
        """
        models = [m for m in [primary, validators["gemini"], validators["claude"]]
                  if m is not None]
        consensus: dict[str, Any] = {}
        consensus_fields: list[str] = []
        disagree_fields: list[str] = []

        for field in MAJOR_FIELDS:
            non_null = [getattr(m, field) for m in models
                        if matching.normalize_ws(getattr(m, field)) != ""]
            if not non_null:
                continue  # nothing visible; do not invent

            if len(models) == 1:
                # Single model: surface its suggestion but do not call it consensus.
                consensus[field] = non_null[0]
                continue

            # Cluster values by fuzzy agreement; pick the largest cluster.
            clusters: list[list[Any]] = []
            for val in non_null:
                placed = False
                for cl in clusters:
                    if matching.values_agree(field, cl[0], val,
                                             self.agree_threshold):
                        cl.append(val)
                        placed = True
                        break
                if not placed:
                    clusters.append([val])

            clusters.sort(key=len, reverse=True)
            top = clusters[0]
            if len(top) >= 2:
                consensus[field] = top[0]
                consensus_fields.append(field)
            else:
                disagree_fields.append(field)

        return consensus, consensus_fields, disagree_fields
