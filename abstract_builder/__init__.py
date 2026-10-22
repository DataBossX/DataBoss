"""abstract_builder — deterministic abstract-package builder (reference-package format).

Modules:
  normalize  field normalizers (Doc No, Book-Page, dates, parties, legals, comments) per the
             operator's standing formatting notes; every change is logged, nothing is invented.
  donor      geometry measured from the Section 11 Overtime donor package (column widths, row
             heights, margins, print setup, fonts).
  render     writes county / BLM index workbooks, 3-band checklist and certification letter in
             donor geometry; converts to ODS/PDF through LibreOffice.
  census     reads any existing index workbook (xlsx/ods) into rows and counts blanks/Unknowns.
  qa         format-compliance gates run on a rendered workbook.
"""
__version__ = "1.0.0"
