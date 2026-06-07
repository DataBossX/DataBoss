"""title_report_factory.

A reusable workflow for building cursory (non-attorney) title-report workbooks
for a single Public Land Survey System tract (Section / Township / Range).

The pipeline is intentionally honest: it only reports what it can tie to a
source document, an existing workbook cell, OCR text, or a logged public
record. Where it has no support, it writes "Unknown" / "Needs Review" rather
than guessing. See README.md for usage.
"""

__version__ = "0.1.0"
