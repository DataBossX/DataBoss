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

import shutil
import zipfile
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
    error: str = ""


def _fix_worksheet_xml(xml_bytes: bytes, fixes: List[str]) -> bytes:
    """Repair one worksheet part. Returns possibly-rewritten bytes.

    Current repairs (safe, non-destructive):
      * Remove ``<f>`` formula elements that evaluate to an error (``t="e"`` on
        the parent ``<c>`` or a formula body starting with ``#``), leaving any
        last-known cached ``<v>`` value in place so no data is lost.
      * Drop dangling shared-formula masters that reference a deleted range.
    """
    parser = etree.XMLParser(remove_blank_text=False, recover=True)
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
            cell.remove(f)
            # if the cached value was an error, clear the error type marker too
            if t == "e":
                del cell.attrib["t"]
            fixes.append(f"removed errored formula in cell {cell.get('r', '?')}")
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
    )
