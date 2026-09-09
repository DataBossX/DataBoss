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
import zipfile
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

try:
    from lxml import etree
    _HAVE_LXML = True
except ImportError:  # pragma: no cover - lxml is a declared dependency
    _HAVE_LXML = False

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS = {"m": _MAIN_NS}


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
    shared_masters = set()
    shared_dependents = []

    for cell in root.iter(f"{{{_MAIN_NS}}}c"):
        formula = cell.find(f"{{{_MAIN_NS}}}f")
        if formula is None:
            continue
        formula_text = (formula.text or "").strip()
        if formula.get("t") == "shared":
            shared_index = formula.get("si")
            if shared_index is None:
                raise ValueError(
                    f"Shared formula in cell {cell.get('r', '?')} has no index"
                )
            if formula_text or formula.get("ref"):
                shared_masters.add(shared_index)
            else:
                shared_dependents.append((shared_index, cell.get("r", "?")))
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

    for shared_index, cell_reference in shared_dependents:
        if shared_index not in shared_masters:
            raise ValueError(
                f"Dangling shared formula in cell {cell_reference}: "
                f"master index {shared_index!r} is missing"
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
