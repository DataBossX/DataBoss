"""Minimal .xlsx writer using only the Python standard library.

An .xlsx file is a ZIP of XML parts (OOXML). This writes a single-sheet workbook
with inline strings (and numbers where values are numeric), which every version
of Excel / LibreOffice / Google Sheets opens. It exists so the pipeline can
ALWAYS emit .xlsx outputs even when openpyxl is not installed — satisfying the
mission's requirement for Excel outputs with zero third-party dependencies.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any, Dict, List, Sequence
from xml.sax.saxutils import escape

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="{name}" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""

_WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""


def _col_letter(idx: int) -> str:
    """1-based column index -> Excel letters (1->A, 27->AA)."""
    s = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def _is_number(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return False
        try:
            float(s)
        except ValueError:
            return False
        # Keep leading-zero identifiers (e.g. "007") as text to avoid data loss.
        return not (len(s) > 1 and s[0] == "0" and s[1] != ".")
    return False


def _cell(ref: str, value: Any) -> str:
    if value is None:
        value = ""
    if _is_number(value):
        return f'<c r="{ref}"><v>{escape(str(value))}</v></c>'
    text = escape(str(value))
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _sheet_xml(fieldnames: Sequence[str], rows: List[Dict[str, Any]]) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    # header
    out.append("<row r=\"1\">")
    for c, name in enumerate(fieldnames, 1):
        out.append(_cell(f"{_col_letter(c)}1", name))
    out.append("</row>")
    # data
    for ri, row in enumerate(rows, 2):
        out.append(f'<row r="{ri}">')
        for c, name in enumerate(fieldnames, 1):
            out.append(_cell(f"{_col_letter(c)}{ri}", row.get(name, "")))
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def write_xlsx(path: Path, fieldnames: Sequence[str], rows: List[Dict[str, Any]], sheet_name: str = "Sheet1") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_name = escape(sheet_name)[:31] or "Sheet1"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _ROOT_RELS)
        z.writestr("xl/workbook.xml", _WORKBOOK.format(name=safe_name))
        z.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        z.writestr("xl/worksheets/sheet1.xml", _sheet_xml(fieldnames, rows))
    return path
