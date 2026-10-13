"""Validate explicitly chosen models for the existing Gemini text workflow.

This module never calls a provider, selects a replacement or certifies account access.
"""
import os
import re


class GeminiModelConfigurationError(ValueError):
    """The text workflow must stay paused for this configuration."""


def resolve_text_model(model=None):
    candidate = os.getenv("GEMINI_MODEL") if model is None else model
    if not isinstance(candidate, str) or not candidate.strip():
        raise GeminiModelConfigurationError(
            "GEMINI_MODEL is not configured; the Google text lane is paused."
        )
    candidate = candidate.strip()
    if candidate.startswith("models/"):
        candidate = candidate[len("models/"):]
    if candidate.startswith(("gemini-omni-", "deep-research-")):
        raise GeminiModelConfigurationError(
            "This identifier requires a separately qualified Interactions workflow; "
            "it cannot be substituted into the text client."
        )
    if candidate in {"gemini-pro", "gemini-pro-vision"} or candidate.startswith("gemini-1."):
        raise GeminiModelConfigurationError(
            "The legacy Gemini identifier is not qualified for this workflow; "
            "choose an explicit owner-verified text model."
        )
    if not re.fullmatch(r"gemini-[a-z0-9][a-z0-9._-]*", candidate):
        raise GeminiModelConfigurationError(
            "Invalid Gemini text model identifier; the Google text lane is paused."
        )
    return candidate

