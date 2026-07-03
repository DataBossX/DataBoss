"""WorkbookManifestBuilder -- assemble an immutable runtime map of the workbook.

The manifest is the read-only object every validator consumes.  It aggregates
ingestion output (structure, ranges, formulas, cached values) with the
classifier's category assignments, plus dependency warnings surfaced from the
cell scan.  Validators read the manifest; they never re-open the file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .sheet_classifier import Classification, SheetCategory, SheetClassifier
from .workbook_ingestor import CellData, IngestResult, RawSheet, WorkbookIngestor


@dataclass
class SheetInfo:
    name: str
    index: int
    category: SheetCategory
    classification_score: int
    headers: list[str]
    header_row: int
    max_row: int
    max_col: int
    cells: dict[str, CellData]

    def formulas(self) -> dict[str, str]:
        return {c.coord: c.formula for c in self.cells.values() if c.formula}

    def numeric_values(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for c in self.cells.values():
            if isinstance(c.value, (int, float)) and not isinstance(c.value, bool):
                out[c.coord] = float(c.value)
        return out

    def cell(self, coord: str) -> Optional[CellData]:
        return self.cells.get(coord)


@dataclass
class WorkbookManifest:
    run_id: str
    version: int
    path: Path
    sha256: str
    zip_ok: bool
    integrity_error: Optional[str]
    zip_parts: list[str]
    sheets: list[SheetInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # -- lookups -----------------------------------------------------------
    def by_category(self, category: SheetCategory) -> list[SheetInfo]:
        return [s for s in self.sheets if s.category == category]

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for s in self.sheets:
            counts[s.category.value] = counts.get(s.category.value, 0) + 1
        return counts

    def get_sheet(self, name: str) -> Optional[SheetInfo]:
        for s in self.sheets:
            if s.name == name:
                return s
        return None

    @property
    def readable(self) -> bool:
        return self.zip_ok and self.integrity_error is None

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "version": self.version,
            "path": str(self.path),
            "sha256": self.sha256,
            "readable": self.readable,
            "integrity_error": self.integrity_error,
            "sheet_count": len(self.sheets),
            "category_counts": self.category_counts(),
            "warnings": self.warnings,
        }


class WorkbookManifestBuilder:
    def __init__(self, ingestor: Optional[WorkbookIngestor] = None,
                 classifier: Optional[SheetClassifier] = None) -> None:
        self.ingestor = ingestor or WorkbookIngestor()
        self.classifier = classifier or SheetClassifier()

    def build(self, run_id: str, version: int, path: str | Path,
              sha256: str) -> WorkbookManifest:
        ingest: IngestResult = self.ingestor.ingest(path, sha256)
        manifest = WorkbookManifest(
            run_id=run_id,
            version=version,
            path=Path(path),
            sha256=sha256,
            zip_ok=ingest.zip_ok,
            integrity_error=ingest.integrity_error,
            zip_parts=ingest.zip_parts,
        )
        if not ingest.readable:
            manifest.warnings.append(
                ingest.integrity_error or "Workbook unreadable.")
            return manifest

        classifications = self.classifier.classify_all(ingest.sheets)
        by_name: dict[str, Classification] = {c.sheet: c for c in classifications}

        for raw in ingest.sheets:
            cls = by_name[raw.name]
            manifest.sheets.append(SheetInfo(
                name=raw.name,
                index=raw.index,
                category=cls.category,
                classification_score=cls.score,
                headers=raw.headers,
                header_row=raw.header_row,
                max_row=raw.max_row,
                max_col=raw.max_col,
                cells=raw.cells,
            ))

        manifest.warnings.extend(self._dependency_warnings(ingest.sheets))
        return manifest

    @staticmethod
    def _dependency_warnings(sheets: list[RawSheet]) -> list[str]:
        """Surface broken references and external links found while scanning."""
        warnings: list[str] = []
        error_tokens = ("#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NAME?", "#NULL!")
        for sheet in sheets:
            for cell in sheet.cells.values():
                if isinstance(cell.value, str) and cell.value in error_tokens:
                    warnings.append(f"{sheet.name}!{cell.coord}: error value "
                                    f"{cell.value}")
                if cell.formula and "[" in cell.formula and "]" in cell.formula:
                    warnings.append(f"{sheet.name}!{cell.coord}: external link in "
                                    f"formula {cell.formula}")
        return warnings
