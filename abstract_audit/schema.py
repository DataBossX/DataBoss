"""Gold-standard schema for Campbell Co. Penterra abstract indexes.

Derived from the Section 15 reference set
(Drive folder ``p15_exact6_reference_20260914``), which is the
turn-in template every other section is measured against.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Header rows that precede the document table, in order.
HEADER_KEYS: tuple[str, ...] = (
    "Index County",
    "Lands",
    "Date",
    "Starting Date",
    "Date Posted Thru",
    "Indexed By",
    "Project",
)

#: Document-table columns, in order.
COLUMNS: tuple[str, ...] = (
    "Document Type",
    "Grantor",
    "Grantee",
    "Doc No",
    "Book-Page",
    "Date of Doc",
    "Rec Date",
    "Legal Description",
    "Comments",
)

#: Columns that must never be blank on a turn-in-ready row.
REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {"Document Type", "Grantor", "Grantee", "Doc No", "Rec Date"}
)

#: Columns legitimately blank on some rows (e.g. modern e-recorded
#: documents carry a Doc No but no Book-Page).
OPTIONAL_COLUMNS: frozenset[str] = frozenset(
    {"Book-Page", "Date of Doc", "Legal Description", "Comments"}
)

#: The six artifacts that make a section deliverable complete.
DELIVERABLE_ARTIFACTS: tuple[str, ...] = (
    "section_index_xlsx",
    "lease_index_xlsx",  # one per federal lease touching the section
    "abstract_checklist_xlsx",
    "certification_letter_docx",
    "certification_letter_pdf",
)


@dataclass(frozen=True)
class SectionSpec:
    """Identity of one section deliverable."""

    section: int
    township: str = "45N"
    range_: str = "76W"
    county: str = "Campbell"
    leases: tuple[str, ...] = field(default_factory=tuple)

    @property
    def slug(self) -> str:
        return f"{self.section}-{self.township}-{self.range_}"

    @property
    def index_filename(self) -> str:
        return (
            f"{self.township}-{self.range_}-{self.section:02d}"
            f"_{self.county}_Co_Penterra_Abstract_Index.xlsx"
        )

    @property
    def checklist_filename(self) -> str:
        return f"Abstract_Checklist_{self.slug}.xlsx"

    def certification_filenames(self) -> tuple[str, str]:
        return (
            f"{self.slug}_Certification_Letter.docx",
            f"{self.slug}_Certification_Letter.pdf",
        )

    def expected_file_count(self) -> int:
        """Section index + checklist + cert docx + cert pdf + one index per lease."""
        return 4 + len(self.leases)


#: Section 15 is the reference: 2 federal leases -> exactly 6 files.
SECTION_15 = SectionSpec(section=15, leases=("WYW-089855", "WYW-021220"))
