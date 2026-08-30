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
import shutil
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


def _fix_worksheet_xml(xml_bytes: bytes, fixes: List[str]) -> bytes:
    """Repair one worksheet part. Returns possibly-rewritten bytes.

    Strict integrity rule: Never downgrade an errored formula (<c t="e"><f>#REF!</f></c>)
    into an ordinary literal cached value. Errored formulas must remain flagged as errors
    or refused, preventing downstream corruption.
    """
    parser = etree.XMLParser(remove_blank_text=False, recover=False)
    root = etree.fromstring(xml_bytes, parser=parser)
    changed = False

    for cell in root.iter(f"{{{_MAIN_NS}}}c"):
        t = cell.get("t")
        f = cell.find(f"{{{_MAIN_NS}}}f")
        if f is None:
            continue
        body = (f.text or "").strip()
        is_error = t == "e" or body.startswith("#") or body.startswith("=#")
        if is_error:
            # Preserve error indicator to prevent downgrading error formulas to fake literals
            if t != "e":
                cell.attrib["t"] = "e"
            fixes.append(f"flagged errored formula in cell {cell.get('r', '?')}")
            changed = True

    if not changed:
        return xml_bytes
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def repair_workbook(
    src: Path,
    dest: Path,
    worksheet_fixer: Optional[Callable[[bytes, List[str]], bytes]] = None,
) -> RepairResult:
    """Copy ``src`` to a new ``dest`` zip, repairing worksheet XML in transit.

    Every non-worksheet part (media, styles, shared strings, drawings, plats) is
    copied verbatim. ``src`` is never modified.
    """
    if not _HAVE_LXML:
        # Degrade gracefully: copy through unchanged rather than crash.
        shutil.copy2(src, dest)
        return RepairResult(output=dest, repaired=False,
                            error="lxml unavailable; copied without repair")

    fixer = worksheet_fixer or _fix_worksheet_xml
    fixes: List[str] = []
    media = 0
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(src, "r") as zin, \
                zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                name = item.filename
                if name.startswith("xl/media/"):
                    media += 1
                if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                    data = fixer(data, fixes)
                # Preserve original metadata (date/compression) for stable output.
                zout.writestr(item, data)
    except (zipfile.BadZipFile, OSError, etree.XMLSyntaxError) as exc:
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
