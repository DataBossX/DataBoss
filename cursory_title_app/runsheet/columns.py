"""Exact Runsheet column map for the Section 31 workbook.

This is the single source of truth for which columns the app may write and
which it must NEVER touch. Columns O..S are live Excel formulas that compute
acreage/interest from the input columns; overwriting them would corrupt the
workbook's math and is strictly forbidden.

Header row is row 1. Data rows start at row 2.
"""
from __future__ import annotations

HEADER_ROW = 1
FIRST_DATA_ROW = 2

# letter -> (header text, writable?)
COLUMNS: dict[str, tuple[str, bool]] = {
    "A": ("Instrument #", True),
    "B": ("OGL", True),
    "C": ("Doc Type", True),
    "D": ("Bk/Pg.", True),
    "E": ("Effective Date", True),
    "F": ("Recorded Date", True),
    "G": ("Grantor", True),
    "H": ("Grantee", True),
    "I": ("Legal Description", True),
    "J": ("Notes", True),
    "K": ("Document Link", True),   # written as an =HYPERLINK(...) formula
    "L": ("Tract(s)", True),
    "M": ("Conveyance type", True),
    "N": ("Conveyance Amount (dec)", True),
    "O": ("GROSS ACRES", False),            # FORMULA - do not write
    "P": ("INTEREST IN", False),            # FORMULA - do not write
    "Q": ("INTEREST OUT", False),           # FORMULA - do not write
    "R": ("TOTAL (Net Ac Conveyed)", False),# FORMULA - do not write
    "S": ("Calc Basis / Flags", False),     # FORMULA - do not write
    "T": ("Review", True),
    "U": ("NEED / ACTION", True),
}

# Columns that carry live formulas and must be preserved untouched.
FORMULA_COLUMNS = [c for c, (_, w) in COLUMNS.items() if not w]

# Columns the writer is allowed to set.
WRITABLE_COLUMNS = [c for c, (_, w) in COLUMNS.items() if w]

# Logical field name -> column letter, for the extraction/data layer.
FIELD_TO_COLUMN = {
    "instrument_number": "A",
    "ogl": "B",
    "doc_type": "C",
    "book_page": "D",
    "effective_date": "E",
    "recorded_date": "F",
    "grantor": "G",
    "grantee": "H",
    "legal_description": "I",
    "notes": "J",
    "document_link": "K",
    "tracts": "L",
    "conveyance_type": "M",
    "conveyance_amount_dec": "N",
    "review": "T",
    "need_action": "U",
}

HEADER_TEXT = {c: h for c, (h, _) in COLUMNS.items()}


def column_for_field(field: str) -> str:
    if field not in FIELD_TO_COLUMN:
        raise KeyError(f"Unknown runsheet field: {field}")
    return FIELD_TO_COLUMN[field]


def assert_writable(col_letter: str) -> None:
    """Hard guard. Raises if a non-writable (formula) column is targeted."""
    col_letter = col_letter.upper()
    if col_letter in FORMULA_COLUMNS:
        raise PermissionError(
            f"Refusing to write column {col_letter} "
            f"({HEADER_TEXT.get(col_letter, '?')}): it is a live formula column."
        )
    if col_letter not in COLUMNS:
        raise PermissionError(f"Refusing to write unknown column {col_letter}.")
