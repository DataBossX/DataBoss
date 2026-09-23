"""Deterministic text edits inside an ODS content.xml tree.

These helpers change only matching paragraph strings. They do not infer
parties, dates, or legal descriptions.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

TEXT_P = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"
TABLE_ROW = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-row"
TABLE_CELL = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-cell"
TABLE_HEADER_ROWS = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-header-rows"


def load_content(ods_path: Path) -> ET.Element:
    with zipfile.ZipFile(ods_path) as archive:
        return ET.fromstring(archive.read("content.xml"))


def paragraph_text(node: ET.Element) -> str:
    return "".join(node.itertext())


def replace_exact_paragraphs(root: ET.Element, replacements: dict[str, str]) -> int:
    """Replace whole-paragraph text when it equals a key. Returns count."""
    changed = 0
    for paragraph in root.iter(TEXT_P):
        current = paragraph_text(paragraph)
        if current in replacements:
            new_value = replacements[current]
            paragraph.clear()
            paragraph.text = new_value
            changed += 1
    return changed


def write_ods(src: Path, dest: Path, root: ET.Element) -> None:
    """Rewrite content.xml and copy every other ODS member unchanged."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(src) as source, zipfile.ZipFile(dest, "w") as out:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "content.xml":
                data = xml_bytes
            out.writestr(info, data)


def count_nonempty_table_rows(root: ET.Element) -> int:
    """Count table rows that have any paragraph text, including header rows."""
    count = 0
    for row in root.iter(TABLE_ROW):
        texts = [paragraph_text(cell) for cell in row.findall(TABLE_CELL)]
        if any(text.strip() for text in texts):
            count += 1
    return count
