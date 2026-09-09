"""XML-based structural repair of .xlsx workbooks using lxml.

Mission section 3 (Repair): when a structural defect is found -- a broken/errored
formula, a stray shared-formula reference, malformed sheet XML -- repair it by
editing the workbook's XML parts directly with :mod:`lxml`, rewriting only the
``xl/worksheets/*.xml`` parts and copying every other part (crucially the
``xl/media/*`` images and embedded plats) byte-for-byte. Editing the OOXML parts
directly -- rather than round-tripping the whole book through a library that
re-encodes images -- is what guarantees no media/plat is corrupted.

An .xlsx is a zip of XML parts. We open it read-only, transform the worksheet
XML in memory, and write a *new* versioned zip (Zero-Destruction) with identical
non-worksheet parts.
"""

from __future__ import annotations

import posixpath
import re
import zipfile
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

try:
    from lxml import etree
    _HAVE_LXML = True
except ImportError:  # pragma: no cover - lxml is a declared dependency
    _HAVE_LXML = False

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS = {"m": _MAIN_NS}
_CELL_REFERENCE = re.compile(r"^\$?([A-Z]{1,3})\$?([1-9]\d*)$")
_CELL_RANGE = re.compile(
    r"^\$?([A-Z]{1,3})\$?([1-9]\d*):\$?([A-Z]{1,3})\$?([1-9]\d*)$"
)


def _column_number(column: str) -> int:
    value = 0
    for character in column:
        value = value * 26 + ord(character) - ord("A") + 1
    return value


def _shared_range_bounds(
    range_reference: str,
) -> Optional[Tuple[int, int, int, int]]:
    area = _CELL_RANGE.fullmatch(range_reference)
    if area is None:
        return None
    min_column, min_row = _column_number(area.group(1)), int(area.group(2))
    max_column, max_row = _column_number(area.group(3)), int(area.group(4))
    if min_column > max_column or min_row > max_row:
        return None
    return min_column, min_row, max_column, max_row


def _shared_range_contains(cell_reference: str, range_reference: str) -> bool:
    cell = _CELL_REFERENCE.fullmatch(cell_reference)
    bounds = _shared_range_bounds(range_reference)
    if cell is None or bounds is None:
        return False
    cell_column, cell_row = _column_number(cell.group(1)), int(cell.group(2))
    min_column, min_row, max_column, max_row = bounds
    return (
        min_column <= cell_column <= max_column
        and min_row <= cell_row <= max_row
    )


def _shared_ranges_overlap(first: str, second: str) -> bool:
    first_bounds = _shared_range_bounds(first)
    second_bounds = _shared_range_bounds(second)
    if first_bounds is None or second_bounds is None:
        return False
    first_min_col, first_min_row, first_max_col, first_max_row = first_bounds
    second_min_col, second_min_row, second_max_col, second_max_row = second_bounds
    return (
        first_min_col <= second_max_col
        and second_min_col <= first_max_col
        and first_min_row <= second_max_row
        and second_min_row <= first_max_row
    )


@dataclass
class RepairResult:
    output: Optional[Path]
    repaired: bool
    fixes: List[str] = field(default_factory=list)
    media_preserved: int = 0
    changed_parts: List[str] = field(default_factory=list)
    error: str = ""


def _fix_worksheet_xml(xml_bytes: bytes, _fixes: List[str]) -> bytes:
    """Inspect one worksheet part and refuse unsafe formula repair.

    An errored formula cannot safely be converted to its cached value. The
    cache may itself be ``#REF!`` or stale, and removing the formula/type marker
    would make that error look like ordinary data. Formula restoration requires
    :func:`restore_formula_from_template`, followed by approved recalculation.
    """
    parser = etree.XMLParser(
        remove_blank_text=False,
        recover=False,
        resolve_entities=False,
        no_network=True,
    )
    root = etree.fromstring(xml_bytes, parser=parser)
    shared_masters = {}
    shared_dependents = []

    for cell in root.iter(f"{{{_MAIN_NS}}}c"):
        formula = cell.find(f"{{{_MAIN_NS}}}f")
        if formula is None:
            continue
        formula_text = (formula.text or "").strip()
        if formula.get("t") == "shared":
            shared_index = formula.get("si")
            cell_reference = cell.get("r", "?")
            if shared_index is None:
                raise ValueError(
                    f"Shared formula in cell {cell_reference} has no index"
                )
            range_reference = formula.get("ref")
            if formula_text:
                if (
                    range_reference is None
                    or not _shared_range_contains(
                        cell_reference, range_reference
                    )
                ):
                    raise ValueError(
                        f"Shared formula master in cell {cell_reference} has "
                        f"invalid range {range_reference!r}"
                    )
                if shared_index in shared_masters:
                    raise ValueError(
                        f"Duplicate shared formula master index "
                        f"{shared_index!r}"
                    )
                shared_masters[shared_index] = range_reference
            elif range_reference is not None:
                raise ValueError(
                    f"Shared formula master in cell {cell_reference} has no "
                    "formula text"
                )
            else:
                shared_dependents.append((shared_index, cell_reference))
        is_error = (
            cell.get("t") == "e"
            or formula_text.startswith("#")
            or formula_text.startswith("=#")
        )
        if is_error:
            raise ValueError(
                f"Unsafe errored formula in cell {cell.get('r', '?')}; "
                "repair refused without template authority"
            )

    master_items = list(shared_masters.items())
    for index, (first_id, first_range) in enumerate(master_items):
        for second_id, second_range in master_items[index + 1:]:
            if _shared_ranges_overlap(first_range, second_range):
                raise ValueError(
                    f"Shared formula master ranges overlap: {first_id!r} "
                    f"{first_range!r} and {second_id!r} {second_range!r}"
                )

    for shared_index, cell_reference in shared_dependents:
        master_range = shared_masters.get(shared_index)
        if master_range is None:
            raise ValueError(
                f"Dangling shared formula in cell {cell_reference}: "
                f"master index {shared_index!r} is missing"
            )
        if not _shared_range_contains(cell_reference, master_range):
            raise ValueError(
                f"Shared formula in cell {cell_reference} is outside master "
                f"range {master_range!r}"
            )

    return xml_bytes


def repair_workbook(
    src: Path,
    dest: Path,
    worksheet_fixer: Optional[Callable[[bytes, List[str]], bytes]] = None,
) -> RepairResult:
    """Validate and copy ``src`` to a new ``dest`` zip.

    Every non-worksheet part (media, styles, shared strings, drawings, plats) is
    copied verbatim. The default worksheet fixer refuses unsafe formula repairs;
    a caller-supplied fixer may apply authorized changes. ``src`` is never
    modified.
    """
    if not _HAVE_LXML:
        return RepairResult(
            output=None,
            repaired=False,
            error="lxml unavailable; workbook repair refused",
        )

    fixer = worksheet_fixer or _fix_worksheet_xml
    fixes: List[str] = []
    media = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_suffix(dest.suffix + ".repairing")

    try:
        if dest.exists():
            raise ValueError(f"Refusing to overwrite existing output: {dest}")
        if temporary.exists():
            temporary.unlink()
        with zipfile.ZipFile(src, "r") as zin, \
                zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                name = item.filename
                if name.startswith("xl/media/"):
                    media += 1
                if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                    data = fixer(data, fixes)
                # Preserve original metadata (date/compression) for stable output.
                zout.writestr(item, data)
        temporary.replace(dest)
    except (zipfile.BadZipFile, OSError, ValueError, etree.XMLSyntaxError) as exc:
        if temporary.exists():
            temporary.unlink()
        return RepairResult(output=None, repaired=False, error=str(exc))

    return RepairResult(
        output=dest,
        repaired=bool(fixes),
        fixes=fixes,
        media_preserved=media,
        changed_parts=["xl/worksheets/*"] if fixes else [],
    )


_DOCUMENT_REL_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _worksheet_part(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = etree.fromstring(archive.read("xl/workbook.xml"))
    sheet = workbook.find(
        f".//{{{_MAIN_NS}}}sheet[@name={sheet_name!r}]"
    )
    if sheet is None:
        raise ValueError(f"Sheet {sheet_name!r} not found")
    relationship_id = sheet.get(f"{{{_DOCUMENT_REL_NS}}}id")
    relationships = etree.fromstring(
        archive.read("xl/_rels/workbook.xml.rels")
    )
    relationship = relationships.find(
        f".//{{{_PACKAGE_REL_NS}}}Relationship[@Id={relationship_id!r}]"
    )
    if relationship is None:
        raise ValueError(f"Relationship for sheet {sheet_name!r} not found")
    target = relationship.get("Target", "")
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join("xl", target))


def restore_formula_from_template(
    staged_path: Path,
    template_path: Path,
    sheet_name: str,
    cell_reference: str,
) -> RepairResult:
    """Restore one formula by editing one OOXML part.

    Every package part except the target worksheet is copied byte-for-byte.
    ``staged_path`` is replaced atomically only after the complete output has
    been written and verified. Cached values are deliberately removed; only an
    approved calculation engine may create a result for the repaired formula.
    """
    if not _HAVE_LXML:
        return RepairResult(
            output=None,
            repaired=False,
            error="lxml unavailable; formula repair refused",
        )

    staged_path = Path(staged_path)
    temporary = staged_path.with_suffix(staged_path.suffix + ".repairing")
    try:
        with zipfile.ZipFile(staged_path, "r") as candidate, zipfile.ZipFile(
            template_path, "r"
        ) as template:
            candidate_part = _worksheet_part(candidate, sheet_name)
            template_part = _worksheet_part(template, sheet_name)
            candidate_root = etree.fromstring(candidate.read(candidate_part))
            template_root = etree.fromstring(template.read(template_part))
            candidate_cell = candidate_root.find(
                f".//{{{_MAIN_NS}}}c[@r={cell_reference!r}]"
            )
            template_cell = template_root.find(
                f".//{{{_MAIN_NS}}}c[@r={cell_reference!r}]"
            )
            if candidate_cell is None or template_cell is None:
                raise ValueError(
                    f"Cell {sheet_name}!{cell_reference} not found in both workbooks"
                )
            template_formula = template_cell.find(f"{{{_MAIN_NS}}}f")
            if template_formula is None:
                raise ValueError(
                    f"Template {sheet_name}!{cell_reference} has no formula authority"
                )

            old_formula = candidate_cell.find(f"{{{_MAIN_NS}}}f")
            old_text = old_formula.text if old_formula is not None else ""
            for tag in ("f", "v"):
                element = candidate_cell.find(f"{{{_MAIN_NS}}}{tag}")
                if element is not None:
                    candidate_cell.remove(element)
            candidate_cell.insert(0, deepcopy(template_formula))
            candidate_cell.attrib.pop("t", None)
            repaired_xml = etree.tostring(
                candidate_root,
                xml_declaration=True,
                encoding="UTF-8",
                standalone=True,
            )

            with zipfile.ZipFile(
                temporary, "w", zipfile.ZIP_DEFLATED
            ) as output:
                for item in candidate.infolist():
                    data = (
                        repaired_xml
                        if item.filename == candidate_part
                        else candidate.read(item.filename)
                    )
                    output.writestr(item, data)

        with zipfile.ZipFile(staged_path, "r") as before, zipfile.ZipFile(
            temporary, "r"
        ) as after:
            if before.namelist() != after.namelist():
                raise ValueError("Formula repair changed workbook package inventory")
            for name in before.namelist():
                if name != candidate_part and before.read(name) != after.read(name):
                    raise ValueError(f"Formula repair changed unexpected part {name}")
        temporary.replace(staged_path)
        return RepairResult(
            output=staged_path,
            repaired=True,
            fixes=[
                f"restored {sheet_name}!{cell_reference} from template "
                f"(previous={old_text!r})"
            ],
            changed_parts=[candidate_part],
        )
    except (OSError, ValueError, zipfile.BadZipFile, etree.XMLSyntaxError) as exc:
        if temporary.exists():
            temporary.unlink()
        return RepairResult(output=None, repaired=False, error=str(exc))
