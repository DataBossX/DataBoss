"""Horizon Command Center.

An autonomous system to ingest, clean, validate, chain and perfect oil & gas
title reports. Built to run *on the machine where the source files live*
(e.g. ``D:\\Desktop\\Horizon``) -- the cloud assistant cannot see that drive,
so this is a portable, testable, run-it-locally package rather than a script
that invents data.

Every module here is import-safe on any OS: nothing touches ``D:\\`` at import
time, all paths are configurable, and the interest math uses exact
``fractions.Fraction`` / ``decimal.Decimal`` (never floats).
"""

from __future__ import annotations

__all__ = [
    "__version__",
    "config",
    "interest",
]

__version__ = "1.0.0"
