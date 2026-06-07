"""title_report_factory - a reusable, config-driven cursory title report pipeline.

Gathers records, (optionally) OCRs documents, classifies instruments, builds a
full-text index, analyzes the chain of title, fills an Excel workbook styled
after a template, and exports a finished report plus machine-readable
confidence and curative-issue artifacts.

Truth rule: never fake perfection. Every record carries a source, a confidence
score, and an issue note when uncertain. Capabilities not available in the
runtime (live county downloads, OCR of image-only PDFs) are detected and logged
as limitations, never faked.
"""

__version__ = "1.0.0"
