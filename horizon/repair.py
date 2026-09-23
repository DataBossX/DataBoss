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
import shutil
import zipfile
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:
    from lxml import etree
    _HAVE_LXML = True
except ImportError:  # pragma: no cover - lxml is a declared dependency
    _HAVE_LXML = False

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS = {"m": _MAIN_NS}
_DOCUMENT_REL_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


class RepairRefused(Exception):
    """Raised when a repair would have to fabricate data to proceed.

    Issue #94 item 1: an error-type cell (``#REF!`` and friends) may only be
    repaired by restoring an approved template formula (Strategy B). If no
    approved template formula exists for that cell, repair must refuse
    outright rather than silently downgrading the error into a plain-looking
    literal. ``defects`` carries a structured entry per refused cell so the
    caller can turn it into a review receipt instead of a crash.
    """

    def __init__(self, message: str, defects: List[Dict[str, str]]):
        super().__init__(message)
        self.defects = defects


@dataclass
class RepairResult:
    output: Optional[Path]
    repaired: bool
    fixes: List[str] = field(default_factory=list)
    media_preserved: int = 0
    changed_parts: List[str] = field(default_factory=list)
    error: str = ""
    # Set when a Strategy-B template-formula restore happened: nothing
    # downstream may trust the (now-absent) cached value for that cell until
    # a real calculation engine (Excel/LibreOffice) recalculates it.
    recalculation_required: bool = False
    # Structured defect/review entries for cells repair refused to touch
    # (e.g. an error cell with no approved template formula authority).
    defects: List[Dict[str, str]] = field(default_factory=list)


def _parse_worksheet_strict_or_prove_lossless(xml_bytes: bytes):
    """Parse worksheet XML strictly, or prove a recovery parse lost nothing.

    lxml's ``recover=True`` mode silently drops or reshapes malformed markup
    -- exactly the kind of silent recovery issue #94 forbids in a
    title-report pipeline: a dropped ``<row>``/``<c>`` must surface as a hard
    defect, never something repair quietly absorbs. So worksheet XML is
    parsed strictly first. Only if that fails do we attempt a recovering
    parse, and even then we accept it only if raw ``<row``/``<c`` tag counts
    in the original bytes exactly match what the recovered tree contains --
    i.e. we can *prove* zero row/cell loss. Otherwise the original strict
    parse error propagates so the caller refuses the repair outright.
    """
    strict_parser = etree.XMLParser(remove_blank_text=False, recover=False)
    try:
        return etree.fromstring(xml_bytes, parser=strict_parser)
    except etree.XMLSyntaxError as strict_exc:
        recover_parser = etree.XMLParser(remove_blank_text=False, recover=True)
        try:
            recovered = etree.fromstring(xml_bytes, parser=recover_parser)
        except etree.XMLSyntaxError:
            recovered = None
        if recovered is None:
            raise strict_exc
        raw_rows = len(re.findall(rb"<(?:[A-Za-z0-9_.-]+:)?row\b", xml_bytes))
        raw_cells = len(re.findall(rb"<(?:[A-Za-z0-9_.-]+:)?c\b", xml_bytes))
        recovered_rows = sum(1 for _ in recovered.iter(f"{{{_MAIN_NS}}}row"))
        recovered_cells = sum(1 for _ in recovered.iter(f"{{{_MAIN_NS}}}c"))
        if recovered_rows != raw_rows or recovered_cells != raw_cells:
            # Recovery reshaped the document -- cannot prove zero row/cell
            # loss, so this is a hard defect, not a silent recovery.
            raise strict_exc
        return recovered


def _cell_is_error(t: Optional[str], formula_body: str, cached_text: str) -> bool:
    return (
        t == "e"
        or formula_body.startswith("#")
        or formula_body.startswith("=#")
        or cached_text.startswith("#")
    )


def _fix_worksheet_xml(
    xml_bytes: bytes,
    fixes: List[str],
    template_formulas: Optional[Dict[str, str]] = None,
    state: Optional[Dict[str, object]] = None,
) -> bytes:
    """Repair one worksheet part. Returns possibly-rewritten bytes.

    STRATEGY B (template-restore, issue #94 item 1). An error-type cell --
    ``t="e"``, a formula body itself beginning with ``#`` (e.g. ``#REF!``),
    or a cached ``<v>`` holding an Excel error code -- must never be
    downgraded to a plain literal. The old behavior (strip ``<f>``, clear
    ``t="e"``, leave the stale cached ``<v>`` behind) made an explicit Excel
    error look like ordinary data to any later pipeline stage -- dangerous in
    a title-report context, and exactly the defect this function now refuses
    to reproduce. Instead:

      * If ``template_formulas`` (an approved-template ``{cell_ref: formula}``
        authority -- see :func:`_extract_template_formulas`) has an entry for
        that cell, the EXACT template formula is restored and the stale
        cached value is dropped. ``state["recalculation_required"]`` is set
        so callers know nothing downstream may trust a cached value until a
        real calculation engine (Excel/LibreOffice) recalculates it.
      * If no approved template formula exists for that cell, repair refuses
        outright by raising :class:`RepairRefused` with a structured defect
        entry per unauthorized cell -- never a silent literal downgrade.
    """
    template_formulas = template_formulas or {}
    root = _parse_worksheet_strict_or_prove_lossless(xml_bytes)
    defects: List[Dict[str, str]] = []
    pending_fixes: List[str] = []
    changed = False

    for cell in root.iter(f"{{{_MAIN_NS}}}c"):
        t = cell.get("t")
        f = cell.find(f"{{{_MAIN_NS}}}f")
        if f is None:
            continue
        v = cell.find(f"{{{_MAIN_NS}}}v")
        body = (f.text or "").strip()
        cached_text = (v.text or "").strip() if v is not None else ""
        if not _cell_is_error(t, body, cached_text):
            continue

        cell_ref = cell.get("r", "?")
        template_formula = template_formulas.get(cell_ref)
        # NB: template_formula is an lxml Element once found -- an Element
        # with no children (e.g. a shared-formula follower's bare <f
        # t="shared" si="N"/>) is falsy under `bool()`, so this must be an
        # explicit `is None` check, never a truthiness check.
        if template_formula is None:
            defects.append({
                "cell": cell_ref,
                "reason": "error_cell_no_template_authority",
                "detail": (
                    f"cell {cell_ref} carries an explicit error "
                    f"(cached={cached_text or '?'!r}, formula={body!r}) and no "
                    "approved template formula exists for this position; "
                    "refusing to downgrade it to a plain literal"
                ),
            })
            continue

        cell.remove(f)
        if v is not None:
            cell.remove(v)
        # Deep-copy the exact template <f> element (preserving t/si/ref and
        # any other attributes), never reconstruct a bare element from text
        # alone -- that would silently corrupt shared/array/data-table
        # formulas. Same pattern as restore_formula_from_template() below.
        cell.insert(0, deepcopy(template_formula))
        cell.attrib.pop("t", None)
        pending_fixes.append(
            f"restored approved template formula in cell {cell_ref} "
            "(flagged for native recalculation, not a cached literal)"
        )
        changed = True

    if defects:
        # Refuse the whole part atomically: never promote a mix of honest
        # template restores and unauthorized literal downgrades.
        raise RepairRefused(
            f"{len(defects)} error cell(s) have no approved template formula "
            "authority; refusing to fabricate a literal in place of an "
            "explicit Excel error",
            defects,
        )

    fixes.extend(pending_fixes)
    if changed and state is not None:
        state["recalculation_required"] = True

    if not changed:
        return xml_bytes
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _sheet_parts(archive: zipfile.ZipFile) -> Dict[str, str]:
    """Return ``{sheet_name: worksheet_part_path}`` for every sheet in the
    workbook, resolved through ``xl/workbook.xml`` and its relationships."""
    workbook = etree.fromstring(archive.read("xl/workbook.xml"))
    relationships = etree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    mapping: Dict[str, str] = {}
    for sheet in workbook.findall(f".//{{{_MAIN_NS}}}sheet"):
        name = sheet.get("name")
        relationship_id = sheet.get(f"{{{_DOCUMENT_REL_NS}}}id")
        if name is None or relationship_id is None:
            continue
        relationship = relationships.find(
            f".//{{{_PACKAGE_REL_NS}}}Relationship[@Id={relationship_id!r}]"
        )
        if relationship is None:
            continue
        target = relationship.get("Target", "")
        part = (
            target.lstrip("/")
            if target.startswith("/")
            else posixpath.normpath(posixpath.join("xl", target))
        )
        mapping[name] = part
    return mapping


def _extract_template_formulas(
    archive: zipfile.ZipFile, part_name: str
) -> Dict[str, "etree._Element"]:
    """Read one approved-template worksheet part and return
    ``{cell_ref: <f> element}`` for every formula cell -- the authority
    source Strategy B restores error cells from.

    The full ``<f>`` element is kept (deep-copied), not just its text: a
    shared/array/data-table formula's ``t``/``si``/``ref`` attributes are
    required to restore it correctly, and a shared-formula *follower* cell's
    ``<f>`` carries no text at all -- only a ``t="shared" si="N"`` reference
    to its master -- so keying on non-empty text would silently drop every
    follower from the template authority.
    """
    root = etree.fromstring(archive.read(part_name))
    formulas: Dict[str, "etree._Element"] = {}
    for cell in root.iter(f"{{{_MAIN_NS}}}c"):
        f = cell.find(f"{{{_MAIN_NS}}}f")
        cell_ref = cell.get("r")
        if f is None or not cell_ref:
            continue
        formulas[cell_ref] = deepcopy(f)
    return formulas


def repair_workbook(
    src: Path,
    dest: Path,
    worksheet_fixer: Optional[Callable[..., bytes]] = None,
    template_path: Optional[Path] = None,
) -> RepairResult:
    """Copy ``src`` to a new ``dest`` zip, repairing worksheet XML in transit.

    Every non-worksheet part (media, styles, shared strings, drawings, plats) is
    copied verbatim. ``src`` is never modified.

    ``template_path``, when given, is an approved-template workbook: its
    per-sheet, per-cell formulas are the only authority Strategy B may
    restore an error cell from (see :func:`_fix_worksheet_xml`). Without a
    template (or without an approved formula for a given error cell), repair
    refuses that cell rather than fabricating a literal -- ``dest`` is never
    written/promoted in that case, and the refusal is returned as a
    structured defect/review receipt (``RepairResult.error`` /
    ``.defects``).
    """
    if not _HAVE_LXML:
        # Degrade gracefully: copy through unchanged rather than crash.
        shutil.copy2(src, dest)
        return RepairResult(output=dest, repaired=False,
                            error="lxml unavailable; copied without repair")

    fixer = worksheet_fixer or _fix_worksheet_xml
    fixes: List[str] = []
    media = 0
    state: Dict[str, object] = {"recalculation_required": False}
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(src, "r") as zin:
            template_formulas_by_part: Dict[str, Dict[str, str]] = {}
            if template_path is not None:
                sheet_parts = _sheet_parts(zin)
                with zipfile.ZipFile(template_path, "r") as ztemplate:
                    template_sheet_parts = _sheet_parts(ztemplate)
                    for sheet_name, part_name in sheet_parts.items():
                        template_part = template_sheet_parts.get(sheet_name)
                        if template_part is not None:
                            template_formulas_by_part[part_name] = (
                                _extract_template_formulas(ztemplate, template_part)
                            )

            with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    name = item.filename
                    if name.startswith("xl/media/"):
                        media += 1
                    if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                        try:
                            data = fixer(
                                data, fixes, template_formulas_by_part.get(name),
                                state,
                            )
                        except TypeError:
                            # A caller-supplied worksheet_fixer using the
                            # legacy 2-arg contract.
                            data = fixer(data, fixes)
                    # Preserve original metadata (date/compression) for stable output.
                    zout.writestr(item, data)
    except RepairRefused as exc:
        if dest.exists():
            dest.unlink()
        return RepairResult(
            output=None, repaired=False, error=str(exc), defects=exc.defects,
        )
    except (zipfile.BadZipFile, OSError, etree.XMLSyntaxError, ValueError,
            KeyError) as exc:
        if dest.exists():
            dest.unlink()
        return RepairResult(output=None, repaired=False, error=str(exc))

    return RepairResult(
        output=dest,
        repaired=bool(fixes),
        fixes=fixes,
        media_preserved=media,
        changed_parts=["xl/worksheets/*"] if fixes else [],
        recalculation_required=bool(state["recalculation_required"]),
    )


def _worksheet_part(archive: zipfile.ZipFile, sheet_name: str) -> str:
    """Resolve one sheet's worksheet part path by name. Shares its
    name/part resolution with :func:`_sheet_parts` so the bulk repair path
    (:func:`repair_workbook`) and the single-cell path
    (:func:`restore_formula_from_template`) agree on which part a sheet name
    means."""
    mapping = _sheet_parts(archive)
    if sheet_name not in mapping:
        raise ValueError(f"Sheet {sheet_name!r} not found")
    return mapping[sheet_name]


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
            recalculation_required=True,
        )
    except (OSError, ValueError, zipfile.BadZipFile, etree.XMLSyntaxError) as exc:
        if temporary.exists():
            temporary.unlink()
        return RepairResult(output=None, repaired=False, error=str(exc))
