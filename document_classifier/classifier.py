"""
classifier.py
-------------
AI-powered document classification using the Anthropic Claude API.

Design choices
~~~~~~~~~~~~~~
* The system prompt is **prompt-cached** (cache_control="ephemeral").  On
  repeated classifications the first request pays a 1.25× write premium;
  every subsequent request reads the same prefix at ~0.1× cost.
* The document text is always placed in the *user* message so it stays
  outside the cached prefix — varying content must not invalidate the cache.
* The client is a module-level singleton to avoid re-initialising TLS and
  connection pools on every call.
* JSON parsing uses a lenient approach: if the model wraps the JSON in a
  markdown fence (``` json … ```), we strip it before parsing.
"""

import json
import logging
import re
from typing import TypedDict

import anthropic

from config import Config

logger = logging.getLogger(__name__)

# ── Singleton client ───────────────────────────────────────────────────────────

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        logger.debug("Anthropic client initialised (model=%s)", Config.MODEL)
    return _client


# ── Return type ────────────────────────────────────────────────────────────────


class ClassificationResult(TypedDict):
    category: str           # one of Config.DOCUMENT_CATEGORIES
    confidence: str         # "High" | "Medium" | "Low"
    summary: str            # 1-2 sentence description
    key_topics: list[str]   # 3-5 specific topics / entities
    reasoning: str          # brief explanation of the decision


# ── Cached system prompt ───────────────────────────────────────────────────────

_CATEGORY_LIST = "\n".join(f"- {c}" for c in Config.DOCUMENT_CATEGORIES)

_SYSTEM_PROMPT = f"""You are an expert document analyst with deep knowledge of business, \
legal, medical, and academic documents.

Your task is to classify a document into exactly ONE of the following categories:

{_CATEGORY_LIST}

Classification rules
--------------------
1. Choose the SINGLE best-matching category from the list above — nothing else.
2. Confidence:
   - "High"   → the category is unambiguous given the content
   - "Medium" → plausible but another category is possible
   - "Low"    → insufficient text or genuinely ambiguous
3. Summary: 1-2 sentences describing the document's purpose and subject matter.
4. Key topics: 3-5 specific topics, entities, or keywords found in the document.
5. Reasoning: brief (1-3 sentences) explanation of why you chose this category.

Output format
-------------
Respond with ONLY a valid JSON object — no markdown fences, no preamble, no trailing text:

{{
  "category":   "<category from the list>",
  "confidence": "<High|Medium|Low>",
  "summary":    "<summary>",
  "key_topics": ["<topic1>", "<topic2>", "<topic3>"],
  "reasoning":  "<reasoning>"
}}"""


# ── Public API ─────────────────────────────────────────────────────────────────


def classify_document(text: str, filename: str) -> ClassificationResult:
    """
    Classify a document using Claude.

    Args:
        text:     Extracted document text (may be long; will be truncated).
        filename: Original filename — provides useful context to the model.

    Returns:
        A ClassificationResult TypedDict.

    Raises:
        RuntimeError: On API errors or unparseable responses.
    """
    client = _get_client()

    truncated_text = text[: Config.MAX_TEXT_CHARS]
    word_count = len(text.split())
    char_count = len(text)

    user_content = (
        f"Filename: {filename}\n"
        f"Document length: ~{word_count:,} words ({char_count:,} characters total; "
        f"showing first {len(truncated_text):,} characters)\n\n"
        f"Document content:\n"
        f"{'─' * 60}\n"
        f"{truncated_text}\n"
        f"{'─' * 60}"
    )

    logger.info(
        "Classifying '%s' — sending %d chars to Claude", filename, len(truncated_text)
    )

    try:
        response = _get_client().messages.create(
            model=Config.MODEL,
            max_tokens=Config.MAX_TOKENS,
            # ── Prompt caching: the system prompt is stable → cache it ─────────
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.AuthenticationError as exc:
        raise RuntimeError(
            "Anthropic authentication failed — check your ANTHROPIC_API_KEY."
        ) from exc
    except anthropic.RateLimitError as exc:
        raise RuntimeError(
            "Anthropic rate limit hit.  Wait a moment and try again."
        ) from exc
    except anthropic.APIError as exc:
        logger.error("Anthropic API error: %s", exc, exc_info=True)
        raise RuntimeError(f"Claude API call failed: {exc}") from exc

    # Log cache efficiency for the first call and subsequent ones
    usage = response.usage
    logger.info(
        "Token usage — input: %d, cache_write: %d, cache_read: %d, output: %d",
        usage.input_tokens,
        getattr(usage, "cache_creation_input_tokens", 0),
        getattr(usage, "cache_read_input_tokens", 0),
        usage.output_tokens,
    )

    raw_text = response.content[0].text.strip()
    logger.debug("Raw model response: %s", raw_text)

    result = _parse_response(raw_text)
    _normalise_result(result)

    logger.info(
        "'%s' → category='%s'  confidence='%s'",
        filename,
        result["category"],
        result["confidence"],
    )
    return result


# ── Private helpers ────────────────────────────────────────────────────────────


def _parse_response(raw: str) -> dict:
    """Parse the model's JSON response, tolerating markdown code fences."""
    # Strip ```json ... ``` or ``` ... ``` wrappers the model sometimes emits
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse model JSON: %s\nRaw text: %s", exc, raw)
        raise RuntimeError(
            "The model returned a non-JSON response.  Please retry."
        ) from exc


def _normalise_result(result: dict) -> None:
    """
    Validate required keys and coerce unexpected values to safe defaults.
    Modifies *result* in place.
    """
    required = {"category", "confidence", "summary", "key_topics", "reasoning"}
    missing = required - result.keys()
    if missing:
        raise RuntimeError(
            f"Model response missing required fields: {sorted(missing)}"
        )

    # Category guard — fall back gracefully rather than crashing
    if result["category"] not in Config.DOCUMENT_CATEGORIES:
        logger.warning(
            "Model returned unknown category '%s' — mapping to 'Other'",
            result["category"],
        )
        result["category"] = "Other"

    # Confidence guard
    if result["confidence"] not in ("High", "Medium", "Low"):
        logger.warning(
            "Model returned unknown confidence '%s' — mapping to 'Low'",
            result["confidence"],
        )
        result["confidence"] = "Low"

    # key_topics must be a list
    if not isinstance(result.get("key_topics"), list):
        result["key_topics"] = [str(result.get("key_topics", ""))]

    # Trim to 5 topics maximum
    result["key_topics"] = result["key_topics"][:5]
