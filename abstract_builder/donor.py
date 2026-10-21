"""Donor geometry — measured from a finished reference package supplied privately by the operator
after LibreOffice conversion of the ODS files. Values are openpyxl width units / points.
Owner instruction (standing notes 2026-10-20) overrides the donor on: font Calibri everywhere, thin black
borders, uniform left/top alignment for all data cells.  DONOR_CENTER_NUMERIC flips numeric/date columns to the
donor's centred alignment if the owner ever asks for it.
"""
from __future__ import annotations

FONT_NAME = "Calibri"
FONT_SIZE = 11
BORDER_STYLE = "thin"          # owner instruction; donor ODS reads as 0.05pt (hair) after conversion
DONOR_CENTER_NUMERIC = False   # owner instruction: uniform left/top; set True for donor centring
DATE_FORMAT = "m/d/yyyy"
INT_FORMAT = "0"

COUNTY_HEADERS = ["Document Type", "Grantor", "Grantee", "Doc No", "Book-Page",
                  "Date of Doc", "Rec Date", "Legal Description", "Comments"]
BLM_HEADERS = ["Document Type", "Grantor", "Grantee", "File No", "Page",
               "Date of Doc", "Rec Date", "Comments", "Legal Description", "Part"]

# measured column widths (openpyxl units)
COUNTY_WIDTHS = [32.85, 36.23, 36.65, 7.92, 7.82, 8.24, 7.92, 37.71, 10.24]
BLM_WIDTHS = [40.95, 42.57, 43.65, 6.89, 5.0, 10.54, 10.13, 10.0, 44.86, 4.33]

COUNTY_NUMERIC_COLS = {4, 5, 6, 7}      # Doc No, Book-Page, Date of Doc, Rec Date (donor centres these)
BLM_NUMERIC_COLS = {4, 5, 6, 7, 10}     # File No, Page, Date of Doc, Rec Date, Part
COUNTY_DATE_COLS = {6, 7}
BLM_DATE_COLS = {6, 7}
COUNTY_INT_COLS = {4}
BLM_INT_COLS = {5, 10}

META_LABELS = ["County:", "Lands:", "Date:", "Starting Date:", "Date Posted Thru:", "Indexed By:", "Project:"]
ROW_HEIGHTS_META = 15.0
ROW_HEIGHT_BLANK8 = 13.8
ROW_HEIGHT_HEADER_COUNTY = 29.85
ROW_HEIGHT_HEADER_BLM = 14.9

PAGE = dict(orientation="landscape", fitToWidth=1, fitToHeight=0, paperSize=1,
            left=0.7, right=0.7, top=0.3, bottom=0.3, header=0.3, footer=0.3)

# Checklist (Abstract_Checklist_11-45N-76W.xlsx): 3 bands, 11 columns
CHECKLIST_SHEET = "Abstract checklist"
CHECKLIST_WIDTHS = [14.0, 18.0, 29.29, 30.14, 38.0, 32.71, 28.0, 18.0, 17.71, 18.86, 15.86]
CHECKLIST_ROW_HEIGHTS = {2: 45.0, 3: 48.0, 5: 30.0, 6: 30.0, 8: 30.0, 9: 78.0}
CHECKLIST_BAND1 = ["County Index", "County Documents", "Plat", "STR online search", "Compare index to Uploads",
                   "BLM File", "SRP", "State File", "Lease Report if applicable",
                   "Reviewed SRP vs BLM file or State file", "Certification Letter"]
CHECKLIST_BAND2 = ["Abstract Excel Sheet", "County", "Lands Covered", "Date Prepared", "Starting Date",
                   "Date Reviewed", "Landman Name", "Project / Prospect"]
CHECKLIST_BAND3 = ["Certification Letter", "Client", "STR & County", "Contents for County Records",
                   "Contents for BLM / State", "SRP Info", "Preparation Date"]
CHECKLIST_LEFT_ALIGNED_ROW9 = {2, 3, 4, 6}   # B9, C9, D9, F9 are left-aligned in the donor
CHECKLIST_PAGE = dict(orientation="landscape", left=0.7, right=0.7, top=0.75, bottom=0.75)

# Certification letter (11-45N-76W_Certification_Letter.docx)
LETTER_PAGE = dict(width_in=8.5, height_in=11.0, left_in=0.98, right_in=0.68, top_in=1.12, bottom_in=0.75)
LETTER_TITLE_PT = 14
LETTER_SUPERSCRIPT_PT = 9
