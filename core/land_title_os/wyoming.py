"""Wyoming abstract-index generation (Move #18).

Format is taken from the verified Campbell County work product
(``47N-75W-05_Campbell_Co_Penterra_Abstract_Index.ods``, "Abstract 4775
Ryder"): a seven-line header block followed by nine columns —
Document Type, Grantor, Grantee, Doc No, Book-Page, Date of Doc, Rec Date,
Legal Description, Comments — in recording order.

Certification letters are populated only from the data passed in and always
end with an unsigned signature block: signing is a human act (Move #83).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .chain_graph import ChainGraph

INDEX_COLUMNS = ["Document Type", "Grantor", "Grantee", "Doc No", "Book-Page",
                 "Date of Doc", "Rec Date", "Legal Description", "Comments"]


@dataclass
class AbstractHeader:
    county: str                    # e.g. "Campbell"
    lands: str                     # e.g. "T47N-R75W Section 05: All"
    date: str                      # preparation date
    posted_thru: str               # county records posted-through date
    indexed_by: str
    project: str                   # e.g. "Abstract 4775 Ryder"
    starting_date: str = "Inception"


def generate_abstract_index(header: AbstractHeader, graph: ChainGraph) -> list[list]:
    """Full sheet rows: header block, column header, then one row per
    instrument in recording order. Blank fields stay blank — never guessed."""
    rows: list[list] = [
        ["Index County:", header.county],
        ["Lands:", header.lands],
        ["Date:", header.date],
        ["Starting Date:", header.starting_date],
        ["Date Posted Thru:", header.posted_thru],
        ["Indexed By:", header.indexed_by],
        ["Project:", header.project],
        INDEX_COLUMNS,
    ]
    for n in sorted(graph.instruments, key=lambda n: (n.date or "9999", n.instrument_id)):
        rows.append([
            n.kind, "; ".join(n.grantors), "; ".join(n.grantees),
            n.instrument_id, n.book_page, "", n.date, n.legal_description, n.notes,
        ])
    return rows


def write_abstract_index_csv(rows: list[list], path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    return p


def missing_document_exceptions(graph: ChainGraph) -> list[str]:
    """Exception list for the certification letter, from chain analysis."""
    out = []
    for f in graph.analyze():
        if f.rule in ("chain_break", "coverage_gap"):
            out.append(f.message)
    return out


def generate_certification_letter(header: AbstractHeader, entry_count: int,
                                  exceptions: list[str], preparer: str) -> str:
    """Certification letter text. Facts come only from the arguments; the
    letter is NOT valid until a human signs the signature block."""
    lines = [
        f"CERTIFICATION — {header.project}",
        "",
        f"Re: Abstract of title records, {header.lands}, {header.county} County, Wyoming.",
        "",
        f"The undersigned certifies that the attached abstract index contains "
        f"{entry_count} entries covering the above-described lands, compiled from the "
        f"records of {header.county} County from {header.starting_date} through "
        f"{header.posted_thru} (the county's posted-through date), prepared "
        f"{header.date}.",
        "",
    ]
    if exceptions:
        lines.append(f"This certification is subject to the following {len(exceptions)} "
                     "exception(s):")
        lines += [f"  {i}. {e}" for i, e in enumerate(exceptions, 1)]
    else:
        lines.append("No missing-document exceptions were identified by automated "
                     "chain analysis. This statement is not a substitute for "
                     "examiner review.")
    lines += [
        "",
        "This index is a finding aid, not a title opinion.",
        "",
        f"Prepared by: {preparer}",
        "Signature: ______________________   Date: ____________",
        "(NOT VALID UNTIL SIGNED — human signature required)",
    ]
    return "\n".join(lines)
