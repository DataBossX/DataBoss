"""
ai_extractors.py
================
Vision-based title extraction and the multi-model router / consensus engine.

- Primary extractor:  OpenAI vision (Responses API style, structured JSON).
- Validator 1:        Gemini vision    (only if GEMINI_API_KEY present).
- Validator 2:        Claude vision    (only if ANTHROPIC_API_KEY present).

The router decides *when* to run validators and merges the results using
2-of-3 field-level agreement. It NEVER invents data and NEVER "cleans up"
names or legal descriptions.

All image data stays in memory (raw PNG bytes). Nothing is written to disk
here.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger("horizon.ai")

# ---------------------------------------------------------------------------
# Extraction schema
# ---------------------------------------------------------------------------

# These are the fields we compare against the spreadsheet. Order matters for
# display only.
EXTRACT_FIELDS: List[str] = [
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
    "county",
    "state",
    "remarks",
]


class TitleExtraction(BaseModel):
    """Strict schema returned by every vision model."""

    instrument_number: Optional[str] = None
    document_type: Optional[str] = None
    book_page: Optional[str] = None
    filed_date: Optional[str] = None
    recorded_date: Optional[str] = None
    effective_date: Optional[str] = None
    grantor: Optional[str] = None
    grantee: Optional[str] = None
    legal_description: Optional[str] = None
    section: Optional[str] = None
    township: Optional[str] = None
    range: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None
    remarks: Optional[str] = None
    confidence: float = 0.0
    uncertain_fields: List[str] = Field(default_factory=list)
    evidence_summary: str = ""
    needs_human_review: bool = True

    @classmethod
    def empty(cls, reason: str = "") -> "TitleExtraction":
        return cls(
            confidence=0.0,
            uncertain_fields=list(EXTRACT_FIELDS),
            evidence_summary=reason,
            needs_human_review=True,
        )


# JSON schema handed to the models for structured output.
JSON_SCHEMA: Dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        **{f: {"type": ["string", "null"]} for f in EXTRACT_FIELDS},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "uncertain_fields": {"type": "array", "items": {"type": "string"}},
        "evidence_summary": {"type": "string"},
        "needs_human_review": {"type": "boolean"},
    },
    "required": EXTRACT_FIELDS
    + ["confidence", "uncertain_fields", "evidence_summary", "needs_human_review"],
}


SYSTEM_PROMPT = """\
You are a meticulous Oklahoma county land-records title examiner.
You are shown one or more page images of a SINGLE recorded county document
(deed, mortgage, lease, assignment, release, affidavit, probate, etc.).

YOUR RULES - read carefully:
- Read ONLY what is actually visible in the document image.
- Do NOT guess. Do NOT use outside knowledge. Do NOT infer from any spreadsheet.
- Preserve names EXACTLY as written: punctuation, initials, middle names,
  marital status ("a single person", "husband and wife"), trustee language
  ("John Doe, Trustee of the Doe Family Trust"), and company suffixes
  (LLC, Inc., L.P., Trust, et ux, et al).
- Preserve legal descriptions carefully. Do NOT over-normalize, reorder,
  abbreviate, or expand them. Copy them as written.
- For book/page, preserve the original formatting if visible (e.g. "BK 1234 PG 56").
- For dates, output strict YYYY-MM-DD ONLY when the date is clearly legible;
  otherwise return null for that date.
- Return null for any field that is not visible or not present.
- Never invent missing data.
- If the image is blurry, cropped, blocked, sideways, watermarked, or
  otherwise hard to read, set confidence LOW and add the affected fields to
  uncertain_fields.
- If multiple conflicting values appear for one field, pick the most likely,
  list that field in uncertain_fields, and explain in evidence_summary.
- confidence is your overall 0..1 certainty for the whole extraction.
- Set needs_human_review=true whenever you are unsure for any reason.

Respond ONLY with a JSON object matching the required schema. No prose.
"""

USER_PROMPT = (
    "Extract the structured title data from this county document. "
    "Follow every rule. Return strict JSON only."
)


def _safe_parse(raw: str) -> TitleExtraction:
    """Parse a model's raw text response into a TitleExtraction."""
    if not raw:
        return TitleExtraction.empty("empty model response")
    text = raw.strip()
    # Strip markdown code fences if present.
    if text.startswith("```"):
        text = text.split("```", 2)[1] if "```" in text[3:] else text
        text = text.lstrip("json").strip().strip("`").strip()
    # Grab the outermost JSON object.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
        return TitleExtraction.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        log.warning("Could not parse model output: %s", exc)
        return TitleExtraction.empty(f"unparseable model output: {exc}")


# ---------------------------------------------------------------------------
# Individual model clients
# ---------------------------------------------------------------------------


class OpenAIVision:
    """Primary extractor using the OpenAI Responses API (vision)."""

    def __init__(self, model: str):
        self.model = model
        self.available = bool(os.getenv("OPENAI_API_KEY"))
        self._client = None
        if self.available:
            try:
                from openai import OpenAI

                self._client = OpenAI()
            except Exception as exc:  # pragma: no cover - import/env guard
                log.error("OpenAI client init failed: %s", exc)
                self.available = False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=16))
    def extract(self, images_png: List[bytes]) -> TitleExtraction:
        if not self.available or not self._client:
            return TitleExtraction.empty("OpenAI not configured")

        content = [{"type": "input_text", "text": USER_PROMPT}]
        for img in images_png:
            b64 = base64.b64encode(img).decode("ascii")
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{b64}",
                }
            )

        # Prefer the Responses API; fall back to chat.completions if needed.
        try:
            resp = self._client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "title_extraction",
                        "schema": JSON_SCHEMA,
                        "strict": True,
                    }
                },
            )
            raw = getattr(resp, "output_text", None) or json.dumps(
                resp.model_dump().get("output", "")
            )
            return _safe_parse(raw)
        except Exception as exc:
            log.warning("Responses API failed (%s); trying chat.completions", exc)
            return self._extract_chat(images_png)

    def _extract_chat(self, images_png: List[bytes]) -> TitleExtraction:
        content = [{"type": "text", "text": USER_PROMPT}]
        for img in images_png:
            b64 = base64.b64encode(img).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                }
            )
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
        )
        return _safe_parse(resp.choices[0].message.content)


class GeminiVision:
    """Validator 1 - Google Gemini vision."""

    def __init__(self, model: str):
        self.model = model
        self.available = bool(os.getenv("GEMINI_API_KEY"))
        self._genai = None
        if self.available:
            try:
                import google.generativeai as genai

                genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                self._genai = genai
            except Exception as exc:  # pragma: no cover
                log.error("Gemini client init failed: %s", exc)
                self.available = False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=16))
    def extract(self, images_png: List[bytes]) -> TitleExtraction:
        if not self.available or not self._genai:
            return TitleExtraction.empty("Gemini not configured")
        model = self._genai.GenerativeModel(
            self.model, system_instruction=SYSTEM_PROMPT
        )
        parts: List = [USER_PROMPT]
        for img in images_png:
            parts.append({"mime_type": "image/png", "data": img})
        resp = model.generate_content(
            parts,
            generation_config={"response_mime_type": "application/json"},
        )
        return _safe_parse(getattr(resp, "text", "") or "")


class ClaudeVision:
    """Validator 2 - Anthropic Claude vision."""

    def __init__(self, model: str):
        self.model = model
        self.available = bool(os.getenv("ANTHROPIC_API_KEY"))
        self._client = None
        if self.available:
            try:
                import anthropic

                self._client = anthropic.Anthropic()
            except Exception as exc:  # pragma: no cover
                log.error("Anthropic client init failed: %s", exc)
                self.available = False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=16))
    def extract(self, images_png: List[bytes]) -> TitleExtraction:
        if not self.available or not self._client:
            return TitleExtraction.empty("Claude not configured")
        content: List[Dict] = [{"type": "text", "text": USER_PROMPT}]
        for img in images_png:
            b64 = base64.b64encode(img).decode("ascii")
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64,
                    },
                }
            )
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=SYSTEM_PROMPT + "\nReturn ONLY the JSON object.",
            messages=[{"role": "user", "content": content}],
        )
        raw = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        return _safe_parse(raw)


# ---------------------------------------------------------------------------
# Router + consensus
# ---------------------------------------------------------------------------

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


def _norm(value: Optional[str]) -> str:
    """Normalize for *comparison only* (never stored)."""
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


class RouterResult:
    """Holds the merged outcome plus bookkeeping for the Excel writer."""

    def __init__(self) -> None:
        self.primary: TitleExtraction = TitleExtraction.empty()
        self.merged: Dict[str, Optional[str]] = {}
        self.consensus_fields: List[str] = []  # fields where >=2 models agree
        self.disagreement_fields: List[str] = []
        self.confidence: float = 0.0
        self.models_used: List[str] = []
        self.validators_used: List[str] = []
        self.needs_human_review: bool = True
        self.evidence_summary: str = ""
        self.uncertain_fields: List[str] = []


class ModelRouter:
    """Coordinates primary extraction + conditional validation + consensus."""

    def __init__(self, config: Dict):
        self.config = config
        self.primary = OpenAIVision(config.get("openai_model", "gpt-5.2"))
        self.gemini = GeminiVision(config.get("gemini_model", "gemini-2.5-pro"))
        self.claude = ClaudeVision(config.get("claude_model", "claude-sonnet-4"))
        self.review_threshold = float(config.get("ai_confidence_review_threshold", 0.85))
        self.always_validate = bool(config.get("always_validate", False))

    def available_summary(self) -> str:
        parts = [
            f"primary(OpenAI)={'yes' if self.primary.available else 'NO'}",
            f"gemini={'yes' if self.gemini.available else 'no'}",
            f"claude={'yes' if self.claude.available else 'no'}",
        ]
        return ", ".join(parts)

    def _should_validate(self, primary: TitleExtraction, row_changed: bool) -> bool:
        """Decide whether to run the validators (see consensus rules)."""
        if self.always_validate:
            return True
        if primary.confidence < self.review_threshold:
            return True
        if primary.needs_human_review:
            return True
        if primary.uncertain_fields:
            return True
        if row_changed and self.config.get("validate_changed_rows", True):
            return True
        return False

    def run(self, images_png: List[bytes], row_changed: bool = False) -> RouterResult:
        """Run the full router. `row_changed` = AI primary differs from sheet."""
        result = RouterResult()

        primary = self.primary.extract(images_png)
        result.primary = primary
        result.models_used.append(self.config.get("openai_model", "openai"))

        extractions: List[Tuple[str, TitleExtraction]] = [("openai", primary)]

        if self._should_validate(primary, row_changed):
            if self.gemini.available:
                g = self.gemini.extract(images_png)
                extractions.append(("gemini", g))
                result.validators_used.append(self.config.get("gemini_model", "gemini"))
            if self.claude.available:
                c = self.claude.extract(images_png)
                extractions.append(("claude", c))
                result.validators_used.append(self.config.get("claude_model", "claude"))

        self._merge(extractions, result)
        return result

    def _merge(
        self, extractions: List[Tuple[str, TitleExtraction]], result: RouterResult
    ) -> None:
        """Field-by-field 2-of-3 consensus. Primary value is the suggestion."""
        primary = extractions[0][1]
        n_models = len(extractions)

        for field in EXTRACT_FIELDS:
            values = [getattr(e, field) for _, e in extractions]
            primary_val = getattr(primary, field)

            if n_models == 1:
                # No validators ran - just carry the primary suggestion through.
                result.merged[field] = primary_val
                continue

            # Count agreement using normalized comparison only.
            buckets: Dict[str, List[Optional[str]]] = {}
            for v in values:
                buckets.setdefault(_norm(v), []).append(v)

            # Find the largest agreeing bucket (ignoring all-empty unless all agree).
            best_key, best_list = max(buckets.items(), key=lambda kv: len(kv[1]))

            if len(best_list) >= 2:
                # >=2 models agree. Use the original (un-normalized) text -
                # prefer the primary's text if it is in the agreeing bucket.
                if _norm(primary_val) == best_key:
                    result.merged[field] = primary_val
                else:
                    result.merged[field] = best_list[0]
                # Only treat NON-empty agreement as real consensus. All models
                # agreeing that a field is absent is not a "correction".
                if field in MAJOR_FIELDS and best_key:
                    result.consensus_fields.append(field)
            else:
                # Models disagree: keep the primary suggestion but flag it.
                result.merged[field] = primary_val
                if field in MAJOR_FIELDS:
                    result.disagreement_fields.append(field)

        # Aggregate confidence = min across models (conservative).
        result.confidence = min(e.confidence for _, e in extractions)
        result.evidence_summary = primary.evidence_summary
        # Union of uncertain fields across all models.
        uncertain = set(primary.uncertain_fields)
        for _, e in extractions[1:]:
            uncertain.update(e.uncertain_fields)
        uncertain.update(result.disagreement_fields)
        result.uncertain_fields = sorted(uncertain)
        result.needs_human_review = (
            any(e.needs_human_review for _, e in extractions)
            or bool(result.disagreement_fields)
            or result.confidence < self.review_threshold
        )
