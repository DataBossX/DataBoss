"""Autonomy levels.

The level is the single number that decides whether a request may only be
explained, drafted, executed read-only, executed as a bounded writer, or
released externally. Level 4 is structurally disabled in Command Brain Alpha —
not merely defaulted off.
"""

from __future__ import annotations

from enum import IntEnum


class AutonomyLevel(IntEnum):
    OBSERVE = 0
    DRAFT = 1
    READ_ONLY_EXECUTE = 2
    BOUNDED_WRITER = 3
    RELEASE_OR_EXTERNAL = 4

    @classmethod
    def parse(cls, value) -> "AutonomyLevel":
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            return cls(value)
        text = str(value).strip().upper().replace("-", "_").replace(" ", "_")
        if text.startswith("LEVEL_"):
            text = text[len("LEVEL_") :]
        if text.isdigit():
            return cls(int(text))
        return cls[text]


#: The highest level Command Brain Alpha will ever grant. Raising this constant
#: is a deliberate, reviewable change — not a runtime configuration knob.
ALPHA_MAX_LEVEL = AutonomyLevel.BOUNDED_WRITER

DESCRIPTIONS = {
    AutonomyLevel.OBSERVE: "Read status and explain. No jobs created.",
    AutonomyLevel.DRAFT: "Create plans, comparison requests, and TaskEnvelope drafts. No execution.",
    AutonomyLevel.READ_ONLY_EXECUTE: (
        "Run approved inspections, OCR, comparisons, tests, and synthetic evaluations."
    ),
    AutonomyLevel.BOUNDED_WRITER: (
        "Execute an explicitly approved TaskEnvelope under a valid lease and fencing token."
    ),
    AutonomyLevel.RELEASE_OR_EXTERNAL: (
        "Promotion, release, sending, publishing, connector writes, or client delivery. "
        "Disabled in Command Brain Alpha."
    ),
}


def is_enabled(level: AutonomyLevel) -> bool:
    return level <= ALPHA_MAX_LEVEL


def describe(level: AutonomyLevel) -> str:
    return DESCRIPTIONS[AutonomyLevel.parse(level)]
