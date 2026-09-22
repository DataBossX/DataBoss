"""Exact page-disposition ledger. Physical pages are not client rows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from .constants import CLIENT_ROW_DISPOSITIONS, DISPOSITIONS
from .hashing import sha256_file
from .pdf_census import PdfCensus, count_pdf_pages

ALLOWED = frozenset(DISPOSITIONS)


@dataclass(frozen=True)
class PageRecord:
    source_path: str
    source_sha256: str
    physical_page: int
    disposition: str
    client_row: bool
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SourceLedger:
    files: list[PdfCensus] = field(default_factory=list)
    pages: list[PageRecord] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def physical_page_count(self) -> int:
        return len(self.pages)

    @property
    def material_start_count(self) -> int:
        return sum(1 for page in self.pages if page.disposition == "MATERIAL_START")

    @property
    def missing_source_count(self) -> int:
        return sum(1 for page in self.pages if page.disposition == "MISSING_SOURCE")

    def to_dict(self) -> dict:
        return {
            "files": [item.to_dict() for item in self.files],
            "pages": [item.to_dict() for item in self.pages],
            "issues": list(self.issues),
            "physical_page_count": self.physical_page_count,
            "material_start_count": self.material_start_count,
            "missing_source_count": self.missing_source_count,
        }


def _validate_disposition(disposition: str) -> str:
    value = disposition.strip().upper()
    if value not in ALLOWED:
        raise ValueError(f"unknown disposition: {disposition!r}")
    return value


def _placeholder_page(census: PdfCensus, disposition: str, notes: str) -> list[PageRecord]:
    return [
        PageRecord(
            source_path=census.path,
            source_sha256=census.sha256,
            physical_page=0,
            disposition=disposition,
            client_row=False,
            notes=notes,
        )
    ]


def assign_pages(
    census: PdfCensus,
    dispositions: list[str] | None = None,
) -> list[PageRecord]:
    """Bind one disposition to each physical page.

    If dispositions are omitted, every page is UNRESOLVED. UNKNOWN is not zero
    and is never auto-promoted to a material start.
    """
    if "MISSING_SOURCE" in census.issues:
        return _placeholder_page(census, "MISSING_SOURCE", "source file not present")
    page_count = census.counted_pages
    if page_count is None:
        return _placeholder_page(census, "UNRESOLVED", "page count unresolved")
    supplied = dispositions or []
    if supplied and len(supplied) != page_count:
        raise ValueError(
            f"disposition count {len(supplied)} != physical pages {page_count}"
        )
    records: list[PageRecord] = []
    for index in range(page_count):
        disposition = (
            _validate_disposition(supplied[index]) if supplied else "UNRESOLVED"
        )
        records.append(
            PageRecord(
                source_path=census.path,
                source_sha256=census.sha256,
                physical_page=index + 1,
                disposition=disposition,
                client_row=disposition in CLIENT_ROW_DISPOSITIONS,
            )
        )
    return records


def build_ledger(
    paths: list[str | Path],
    dispositions_by_file: dict[str, list[str]] | None = None,
) -> SourceLedger:
    ledger = SourceLedger()
    dispositions_by_file = dispositions_by_file or {}
    for raw in paths:
        path = Path(raw)
        census = count_pdf_pages(path)
        ledger.files.append(census)
        assigned = assign_pages(census, dispositions_by_file.get(path.name))
        ledger.pages.extend(assigned)
        if not census.agree:
            ledger.issues.append(f"{path.name}: page count unresolved")
        if not path.exists():
            ledger.issues.append(f"{path.name}: MISSING_SOURCE")
    seen: set[tuple[str, int]] = set()
    for page in ledger.pages:
        if page.disposition != "MATERIAL_START":
            continue
        identity = (page.source_sha256, page.physical_page)
        if identity in seen:
            ledger.issues.append(
                f"duplicate physical-start {page.source_path} p{page.physical_page}"
            )
        seen.add(identity)
    return ledger


def hash_tree(
    root: str | Path,
    suffixes: tuple[str, ...] = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"),
) -> list[dict]:
    """Inventory files under root with SHA-256. Empty root is an access issue."""
    base = Path(root)
    if not base.exists():
        return []
    records = []
    for path in sorted(path for path in base.rglob("*") if path.is_file()):
        if path.suffix.lower() not in suffixes:
            continue
        records.append(
            {
                "path": str(path.relative_to(base)),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return records
