"""Deterministic, reusable verification tools for the Penterra abstract program.

Design rules (from the 2026-09-14 completion mandate):
  * SOURCE PIXELS > newest exact-target receipt > deterministic/native QA > model.
  * UNKNOWN != ZERO. A blank is classified, never silently filled.
  * One mutable target = one writer.
  * Tools are pure/read-only. They never modify canonical source files.
"""
__all__ = [
    "stable_key", "identity", "pdf_census", "dupe_pages",
    "blanks", "parity", "package", "replay", "lease",
]
