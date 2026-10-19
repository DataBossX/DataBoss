"""PEACHES — deterministic local audit/QA pipeline.

Honesty rules (enforced in code and docs):
- Machine-detected document boundaries are CANDIDATEs, never verified.
- OCR-located or OCR-only pages are never reported as visually reviewed.
- No check is reported as passed unless it was actually executed.
"""

__version__ = "2.0.0"
