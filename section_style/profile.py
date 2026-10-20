"""Layout constants measured from the Section 11 abstract index.

These are column widths, fonts, page setup, and header labels only.
They contain no project, party, or tract facts.
"""

from __future__ import annotations

COUNTY_HEADERS = (
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

FEDERAL_HEADERS = (
    "Document Type",
    "Grantor",
    "Grantee",
    "File No",
    "Page",
    "Date of Doc",
    "Rec Date",
    "Comments",
    "Legal Description",
    "Part",
)

# ODS column widths converted at 0.231 cm per Excel width unit.
COUNTY_WIDTHS = (35.61, 39.27, 39.73, 8.59, 8.47, 8.93, 8.59, 40.88, 11.1)
FEDERAL_WIDTHS = (40.95, 42.57, 43.65, 6.89, 5.0, 10.54, 10.13, 10.0, 44.86, 4.33)

# Checklist grid used by the Section 11 abstract checklist, in character units.
CHECKLIST_WIDTHS = (14.0, 18.0, 29.29, 30.14, 38.0, 32.71, 28.0, 18.0, 17.71, 18.86, 15.86)

FONT_NAME = "Calibri"
FONT_SIZE = 11
FONT_COLOR = "000000"
BORDER_COLOR = "000000"
DATE_FORMAT = "m/d/yyyy"
INTEGER_FORMAT = "0"

# Page setup from the Section 11 index page layout. Paper size 1 is US Letter.
PAPER_LETTER = 1
MARGIN_LEFT = 0.7
MARGIN_RIGHT = 0.7
MARGIN_TOP = 0.3
MARGIN_BOTTOM = 0.3
MARGIN_HEADER = 0.3
MARGIN_FOOTER = 0.3

META_ROW_HEIGHT = 15.0
HEADER_ROW_HEIGHT = 30.0
ROW_HEIGHT_STEP = 15.0
MAX_DATA_ROW_HEIGHT = 150.0
CHECKLIST_SCALE = 45

CENTER_NO_WRAP = {"Doc No", "Book-Page", "File No", "Page", "Part"}
DATE_HEADERS = {"Date of Doc", "Rec Date"}
CHECKLIST_MARKER = "County Index"
