"""Model provider abstraction. Vision/extraction is the only thing models do
here, and every provider implements the same tiny contract so they are
swappable (Claude / OpenAI / Gemini / local OCR) with retry + fallback.
"""
from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from pathlib import Path


class ModelResult(dict):
    """A plain dict with a couple of guaranteed keys."""

    @property
    def confidence(self) -> float:
        try:
            return float(self.get("confidence", self.get("confidence_score", 0.0)) or 0.0)
        except (TypeError, ValueError):
            return 0.0


class VisionProvider(ABC):
    name = "base"

    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    def extract_json(self, image_paths: list[str], instruction: str) -> ModelResult:
        """Send page image(s) + instruction, return parsed JSON as ModelResult.
        Must raise on transport/auth failure so the registry can fall back."""
        ...

    @staticmethod
    def _b64(image_path: str) -> tuple[str, str]:
        p = Path(image_path)
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        return base64.b64encode(p.read_bytes()).decode(), mime
