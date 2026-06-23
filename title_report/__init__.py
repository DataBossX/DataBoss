"""Cursory title report generator.

A self-contained engine that turns a structured title-examination data model
into the full deliverable set described in the DataBoss report workflow:

  * an Excel workbook with every required tab (cover, source log, runsheet,
    instrument abstractions, mineral/surface chain, leasehold/WI/burdens chain,
    well/HBP schedule, encumbrances & curative, NRI/WI matrix, QA dashboard,
    missing/unverified instruments) using live spreadsheet formulas;
  * SOURCE_LOG.csv, CURATIVE_LIST.csv, MISSING_OR_UNVERIFIED_INSTRUMENTS.csv;
  * QA_RESULTS.md and CHANGE_SUMMARY.md.

The module ships with an illustrative, clearly-flagged placeholder dataset for
Section 31-11N-24W, Roger Mills County, OK so the pipeline runs end to end with
no live source access. Swap in a real ``TitleReport`` to produce a real report.

Design rules enforced throughout (see ``qa.py``):
  * Unknown fields stay ``UNKNOWN`` -- never inferred.
  * NRI/WI/royalty arithmetic uses exact rational math (``fractions.Fraction``)
    and is mirrored as auditable Excel formulas; nothing is computed without
    exact governing language.
  * Every material fact carries a citation to a source row/page.
"""

from .models import (
    UNKNOWN,
    ProjectConfig,
    Source,
    Instrument,
    Abstraction,
    ChainLink,
    Well,
    Curative,
    OwnershipEntry,
    TitleReport,
)

__all__ = [
    "UNKNOWN",
    "ProjectConfig",
    "Source",
    "Instrument",
    "Abstraction",
    "ChainLink",
    "Well",
    "Curative",
    "OwnershipEntry",
    "TitleReport",
]

__version__ = "0.1.0"
