"""Section-15 parity: compare presentation only, never facts."""
from __future__ import annotations

# Presentation attributes that may be compared to the Section 15 donor.
FORMAT_KEYS = ("font_name", "font_size", "border_style", "wrap_text",
               "column_widths", "title_rows", "print_area", "margins",
               "repeated_headings", "scaling", "fit_to_width", "orientation",
               "paper_size", "page_breaks", "certification_pages")
# Fact-bearing attributes that must NEVER be copied from Section 15.
FACT_KEYS = ("county_rows", "federal_rows", "dates", "parties", "counts",
             "doc_numbers", "legal_descriptions", "serials")


class ParityViolation(RuntimeError):
    pass


def compare(candidate: dict, donor: dict, *, known_donor_defects: set[str] = frozenset()) -> dict:
    """Compare presentation keys only. Raises if a fact key is offered."""
    leaked = (set(candidate) | set(donor)) & set(FACT_KEYS)
    if leaked:
        raise ParityViolation(
            f"fact-bearing keys must not enter a parity comparison: {sorted(leaked)}")

    matches, diffs, skipped = [], [], []
    for k in FORMAT_KEYS:
        if k not in candidate or k not in donor:
            continue
        if k in known_donor_defects:
            skipped.append({"key": k, "reason": "donor defect; do not inherit",
                            "candidate": candidate[k], "donor": donor[k]})
            continue
        (matches if candidate[k] == donor[k] else diffs).append(
            {"key": k, "candidate": candidate[k], "donor": donor[k]})

    return {"matches": matches, "differences": diffs, "skipped_donor_defects": skipped,
            "compared": len(matches) + len(diffs),
            "parity": not diffs}
