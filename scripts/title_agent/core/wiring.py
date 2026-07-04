"""Concrete adapters that bind the layers into a runnable agent — the wiring.

The loop (Phase 6) depends on three injected protocols; this module supplies
production implementations of all three:

* ``WorkbookGateSuite`` (a ``GateEvaluator``) reads a workbook version via the
  ingestion mapper, extracts typed inputs, and runs the Phase-5 validators.
* ``SurgeonRepairer`` (a ``Repairer``) applies Category A fixes with the
  Phase-3 XML surgery and recalculation.
* ``OKCountySourceProbe`` (a ``SourceProbe``) wires the Phase-2 client, verifier,
  and budget manager behind the Gate-4 interface.

All workbook-layout knowledge lives here, behind a configurable ``ColumnMap``
that resolves logical fields to columns **by header label** (not fixed index),
so retargeting to the real Roger Mills file is a matter of adjusting aliases,
not touching validators. The convention this expects:

* Each ``Tract N`` sheet lists instruments with columns matching Grantor,
  Grantee, Date, Interest Change (signed, for conservation), Book, Page,
  Instrument.
* A recap/summary sheet has one row per tract: Tract, Gross Acres, Interest
  Fraction, Net Acres (for pro-rata footing).
* The OGL register lists Tract, Lessor, Royalty; the Working-Interest sheet
  lists Tract, Owner, WI, NRI.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from lxml import etree

from ..core.config import GROSS_ACRE_TARGET
from ..core.taxonomy import FailureCategory, Gate
from ..data.ingestion import SheetKind, SheetProfile, WorkbookMapper, WorkbookTopology
from ..excel.recalc import LibreOfficeEngine
from ..excel.xml_surgeon import ArchiveManager, CalcChainDestroyer, XMLPatcher
from ..validators.rules import (
    AcreageFooting,
    ChainContinuity,
    ChainInstrument,
    Failure,
    InstrumentLine,
    InterestConservation,
    OGLAudit,
    OGLEntry,
    SourceAudit,
    SourceProbe,
    SourceProbeResult,
    TractAcreage,
    WIEntry,
)

_NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


# --------------------------------------------------------------------------- #
# Column mapping (header-label based, configurable)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ColumnMap:
    """Alias lists per logical field. A field resolves to the first header
    whose normalized text contains any alias. Adjust here to retarget."""

    grantor: tuple[str, ...] = ("grantor",)
    grantee: tuple[str, ...] = ("grantee",)
    date: tuple[str, ...] = ("date",)
    interest_change: tuple[str, ...] = ("interest change", "net interest", "conveyed")
    book: tuple[str, ...] = ("book",)
    page: tuple[str, ...] = ("page",)
    instrument: tuple[str, ...] = ("instrument", "type")
    tract: tuple[str, ...] = ("tract",)
    gross_acres: tuple[str, ...] = ("gross acres", "gross")
    net_acres: tuple[str, ...] = ("net acres", "net")
    interest_fraction: tuple[str, ...] = ("interest fraction", "fraction", "mineral interest")
    lessor: tuple[str, ...] = ("lessor",)
    royalty: tuple[str, ...] = ("royalty",)
    owner: tuple[str, ...] = ("owner",)
    working_interest: tuple[str, ...] = ("working interest", "wi")
    nri: tuple[str, ...] = ("nri", "net revenue")

    @classmethod
    def from_mapping(cls, data: Mapping[str, Sequence[str]]) -> "ColumnMap":
        """Build a ColumnMap from a {field: [aliases]} mapping, overriding only
        the fields provided and keeping the defaults for the rest. This lets an
        operator retarget the layout to a real workbook by editing a small
        config file — no code change. Unknown field names are rejected so a
        typo fails loudly rather than being silently ignored."""
        known = {f.name for f in dataclasses.fields(cls)}
        kwargs: dict[str, tuple[str, ...]] = {}
        for name, aliases in data.items():
            if name not in known:
                raise ValueError(
                    f"unknown ColumnMap field {name!r}; valid fields: {sorted(known)}")
            if isinstance(aliases, str) or not isinstance(aliases, Sequence):
                raise ValueError(f"aliases for {name!r} must be a list of strings")
            cleaned = tuple(str(a).strip() for a in aliases if str(a).strip())
            if not cleaned:
                raise ValueError(f"field {name!r} has no non-empty aliases")
            kwargs[name] = cleaned
        return cls(**kwargs)

    @classmethod
    def from_json(cls, path: Path) -> "ColumnMap":
        """Load a ColumnMap from a JSON file of {field: [aliases]}. JSON (not
        TOML) keeps this dependency-free on Python 3.10."""
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"column map file must be a JSON object: {path}")
        return cls.from_mapping(raw)


def _norm(text: Any) -> str:
    return str(text).strip().lower() if text is not None else ""


def _col_letter(index0: int) -> str:
    """0-based column index -> Excel letter."""
    idx = index0 + 1
    letters = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


class _Header:
    """Resolves logical fields to column indices for one sheet's header row."""

    def __init__(self, header_cells: Sequence[Any]) -> None:
        self._labels = [_norm(c) for c in header_cells]

    def resolve(self, aliases: Sequence[str]) -> Optional[int]:
        for alias in aliases:
            a = alias.lower()
            for idx, label in enumerate(self._labels):
                if label and a in label:
                    return idx
        return None


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _FootingRefs:
    """Cell references used to auto-repair a pro-rata footing formula."""

    sheet: str
    net_cell: str
    gross_cell: str
    fraction_cell: str


class WorkbookExtractor:
    """Turns a workbook version into typed validator inputs."""

    def __init__(self, column_map: Optional[ColumnMap] = None) -> None:
        self._cm = column_map or ColumnMap()
        self._mapper = WorkbookMapper()

    def resolve_fields(
        self, path: Path, sheet: SheetProfile, fields: Mapping[str, Sequence[str]]
    ) -> tuple[dict[str, Optional[int]], int]:
        """Resolve each named field to a column on ``sheet`` and count data
        rows. Returns ({field: col_or_None}, data_row_count). Used by the
        coverage preflight to distinguish 'column absent' (a mapping problem)
        from 'column present but no rows' (a legitimately empty sheet)."""
        if sheet.header_row is None:
            return {name: None for name in fields}, 0
        grid = self._mapper.read_grid(path, sheet.name)
        hdr = _Header(grid[sheet.header_row - 1])
        resolved = {name: hdr.resolve(aliases) for name, aliases in fields.items()}
        rows = len(self._data_rows(grid, sheet.header_row))
        return resolved, rows

    def _data_rows(self, grid: Sequence[Sequence[Any]], header_row: int) -> list[tuple[int, Sequence[Any]]]:
        """Return (excel_row_number, row) for each non-empty row below the
        header. ``header_row`` is 1-based."""
        out: list[tuple[int, Sequence[Any]]] = []
        for offset, row in enumerate(grid[header_row:], start=header_row + 1):
            if any(c is not None and str(c).strip() for c in row):
                out.append((offset, row))
        return out

    def interest_changes(self, path: Path, sheet: SheetProfile) -> list[float]:
        if sheet.header_row is None:
            return []
        grid = self._mapper.read_grid(path, sheet.name)
        hdr = _Header(grid[sheet.header_row - 1])
        col = hdr.resolve(self._cm.interest_change)
        if col is None:
            return []
        values: list[float] = []
        for _, row in self._data_rows(grid, sheet.header_row):
            if col < len(row) and isinstance(row[col], (int, float)):
                values.append(float(row[col]))
        return values

    def chain(self, path: Path, sheet: SheetProfile) -> list[ChainInstrument]:
        if sheet.header_row is None:
            return []
        grid = self._mapper.read_grid(path, sheet.name)
        hdr = _Header(grid[sheet.header_row - 1])
        g, gr, d = (hdr.resolve(self._cm.grantor), hdr.resolve(self._cm.grantee),
                    hdr.resolve(self._cm.date))
        if g is None or gr is None:
            return []
        out: list[ChainInstrument] = []
        for seq, (_, row) in enumerate(self._data_rows(grid, sheet.header_row), start=1):
            out.append(ChainInstrument(
                seq=seq,
                grantor=str(row[g]) if g < len(row) and row[g] is not None else "",
                grantee=str(row[gr]) if gr < len(row) and row[gr] is not None else "",
                instrument_date=(str(row[d]) if d is not None and d < len(row) and row[d] else None),
            ))
        return out

    def instrument_lines(self, path: Path, sheet: SheetProfile) -> list[InstrumentLine]:
        if sheet.header_row is None:
            return []
        grid = self._mapper.read_grid(path, sheet.name)
        hdr = _Header(grid[sheet.header_row - 1])
        b, p, it = (hdr.resolve(self._cm.book), hdr.resolve(self._cm.page),
                    hdr.resolve(self._cm.instrument))
        if b is None or p is None:
            return []
        out: list[InstrumentLine] = []
        for seq, (_, row) in enumerate(self._data_rows(grid, sheet.header_row), start=1):
            itype = str(row[it]) if it is not None and it < len(row) and row[it] else None
            out.append(InstrumentLine(
                seq=seq,
                book=str(row[b]) if b < len(row) and row[b] is not None else "",
                page=str(row[p]) if p < len(row) and row[p] is not None else "",
                instrument_type=itype,
                workbook_has_metadata=bool(itype),
            ))
        return out

    def recap_sheet(self, topology: WorkbookTopology, path: Path) -> Optional[SheetProfile]:
        """Find the tract recap: a sheet whose header carries a gross-acres and
        a tract column. Prefer names hinting recap/summary."""
        candidates: list[SheetProfile] = []
        for s in topology.sheets:
            if s.header_row is None:
                continue
            hdr = _Header(s.headers)
            if hdr.resolve(self._cm.gross_acres) is not None and hdr.resolve(self._cm.tract) is not None:
                candidates.append(s)
        if not candidates:
            return None
        candidates.sort(key=lambda s: (0 if any(k in s.name.lower()
                        for k in ("recap", "summary")) else 1))
        return candidates[0]

    def tract_acreage(
        self, path: Path, recap: SheetProfile
    ) -> list[tuple[TractAcreage, _FootingRefs]]:
        grid = self._mapper.read_grid(path, recap.name)
        assert recap.header_row is not None
        hdr = _Header(grid[recap.header_row - 1])
        tcol = hdr.resolve(self._cm.tract)
        gcol = hdr.resolve(self._cm.gross_acres)
        fcol = hdr.resolve(self._cm.interest_fraction)
        ncol = hdr.resolve(self._cm.net_acres)
        if tcol is None or gcol is None or fcol is None or ncol is None:
            return []
        out: list[tuple[TractAcreage, _FootingRefs]] = []
        for excel_row, row in self._data_rows(grid, recap.header_row):
            tract_no = self._as_int(row[tcol]) if tcol < len(row) else None
            gross = self._as_float(row[gcol]) if gcol < len(row) else None
            frac = self._as_float(row[fcol]) if fcol < len(row) else None
            if tract_no is None or gross is None or frac is None:
                continue  # a totals/blank row, not a tract line
            net = self._as_float(row[ncol]) if ncol < len(row) else None
            refs = _FootingRefs(
                sheet=recap.name,
                net_cell=f"{_col_letter(ncol)}{excel_row}",
                gross_cell=f"{_col_letter(gcol)}{excel_row}",
                fraction_cell=f"{_col_letter(fcol)}{excel_row}",
            )
            out.append((TractAcreage(tract_no, gross, frac, net), refs))
        return out

    def ogl_entries(self, path: Path, topology: WorkbookTopology) -> list[OGLEntry]:
        sheet = topology.ogl_register()
        if sheet is None or sheet.header_row is None:
            return []
        grid = self._mapper.read_grid(path, sheet.name)
        hdr = _Header(grid[sheet.header_row - 1])
        tcol, lcol, rcol = (hdr.resolve(self._cm.tract), hdr.resolve(self._cm.lessor),
                            hdr.resolve(self._cm.royalty))
        if tcol is None or rcol is None:
            return []
        out: list[OGLEntry] = []
        for _, row in self._data_rows(grid, sheet.header_row):
            t, r = self._as_int(row[tcol]) if tcol < len(row) else None, \
                   self._as_float(row[rcol]) if rcol < len(row) else None
            if t is None or r is None:
                continue
            lessor = str(row[lcol]) if lcol is not None and lcol < len(row) and row[lcol] else ""
            out.append(OGLEntry(t, lessor, r))
        return out

    def wi_entries(self, path: Path, topology: WorkbookTopology) -> list[WIEntry]:
        out: list[WIEntry] = []
        for sheet in topology.working_interest_sheets():
            if sheet.header_row is None:
                continue
            grid = self._mapper.read_grid(path, sheet.name)
            hdr = _Header(grid[sheet.header_row - 1])
            tcol = hdr.resolve(self._cm.tract)
            ocol = hdr.resolve(self._cm.owner)
            wcol = hdr.resolve(self._cm.working_interest)
            ncol = hdr.resolve(self._cm.nri)
            if tcol is None or wcol is None or ncol is None:
                continue
            for _, row in self._data_rows(grid, sheet.header_row):
                t = self._as_int(row[tcol]) if tcol < len(row) else None
                wi = self._as_float(row[wcol]) if wcol < len(row) else None
                nri = self._as_float(row[ncol]) if ncol < len(row) else None
                if t is None or wi is None or nri is None:
                    continue
                owner = str(row[ocol]) if ocol is not None and ocol < len(row) and row[ocol] else ""
                out.append(WIEntry(t, owner, wi, nri))
        return out

    @staticmethod
    def _as_int(v: Any) -> Optional[int]:
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_float(v: Any) -> Optional[float]:
        if isinstance(v, bool):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None


# --------------------------------------------------------------------------- #
# GateEvaluator implementation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CoverageItem:
    """Whether a gate's inputs could actually be mapped on a given sheet."""

    gate: str
    sheet: str
    status: str  # "mapped" | "columns_unresolved" | "sheet_absent"
    missing_columns: tuple[str, ...]
    data_rows: int
    note: str = ""


@dataclass(frozen=True)
class CoverageReport:
    """Result of the mapping preflight.

    ``ok`` is False when any *blocking* condition holds — a core gate (2 or 3)
    whose inputs cannot be read from a sheet that exists. Running the gate suite
    on such a workbook would let those gates pass on no data and produce a false
    CERTIFIED, so the loop must not be trusted until the mapping is fixed.
    """

    items: tuple[CoverageItem, ...]
    blocking: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.blocking


class WorkbookGateSuite:
    """Runs all applicable gates against a workbook version.

    Gates 1-5 always run. Gate 6 (Execution) runs only when a functional
    recalc engine is supplied — otherwise it is skipped, never faked, so the
    absence of a working LibreOffice can never be mistaken for a pass.

    Before trusting a certification, call ``coverage(path)``: it confirms the
    workbook's columns actually map to the validators' inputs, so a mismatched
    layout surfaces as a blocking preflight error rather than a silent pass.
    """

    def __init__(
        self,
        column_map: Optional[ColumnMap] = None,
        source_probe: Optional[SourceProbe] = None,
        recalc_engine: Optional[LibreOfficeEngine] = None,
        *,
        gross_target: float = GROSS_ACRE_TARGET,
    ) -> None:
        self._column_map = column_map or ColumnMap()
        self._extractor = WorkbookExtractor(self._column_map)
        self._mapper = WorkbookMapper()
        self._probe = source_probe
        self._recalc = recalc_engine
        self._gross_target = gross_target
        self._interest = InterestConservation()
        self._acreage = AcreageFooting()
        self._chain = ChainContinuity()
        self._source = SourceAudit()
        self._ogl = OGLAudit()

    def evaluate(self, version: Any) -> list[Failure]:
        path = Path(version.file_path)
        topology = self._mapper.map(path)
        failures: list[Failure] = []

        # Gate 2 — acreage footing (recap sheet).
        recap = self._extractor.recap_sheet(topology, path)
        if recap is not None:
            pairs = self._extractor.tract_acreage(path, recap)
            for acreage, refs in pairs:
                res = self._acreage.verify_pro_rata(acreage)
                failures.extend(self._enrich_footing(res.failures, refs))
            if pairs:
                failures.extend(self._acreage.verify_gross_total(
                    [a for a, _ in pairs], target=self._gross_target).failures)

        # Gates 1, 3, 4 — per tract sheet.
        for tract in topology.tracts():
            ref = tract.name
            changes = self._extractor.interest_changes(path, tract)
            if changes:
                failures.extend(self._interest.check_zero_sum(changes, ref).failures)
            chain = self._extractor.chain(path, tract)
            if chain:
                failures.extend(self._chain.check_gapless_chain(chain, ref).failures)
            if self._probe is not None:
                lines = self._extractor.instrument_lines(path, tract)
                if lines:
                    failures.extend(
                        self._source.verify_instrument_lines(lines, self._probe, ref).failures)

        # Gate 5 — OGL parity.
        ogl = self._extractor.ogl_entries(path, topology)
        wi = self._extractor.wi_entries(path, topology)
        if ogl or wi:
            failures.extend(self._ogl.validate_ogl_register(ogl, wi).failures)

        # Gate 6 — execution (only if a functional engine is present).
        if self._recalc is not None and self._recalc.conversion_works():
            result = self._recalc.run_headless_recalc(path)
            for err in result.errors:
                failures.append(Failure(
                    gate=Gate.EXECUTION, category=FailureCategory.XML_STATE_ERROR,
                    reference=f"{err.sheet}!{err.cell}",
                    detail=f"calc error {err.value}", proof={"sheet": err.sheet}))
            if result.oom:
                failures.append(Failure(
                    gate=Gate.EXECUTION, category=FailureCategory.XML_STATE_ERROR,
                    reference=str(path.name), detail="recalc OOM / timeout", proof={}))

        return failures

    def coverage(self, path: Path) -> CoverageReport:
        """Preflight: verify the workbook's columns map to the gate inputs.

        Blocking (a false-certify risk) when a *core* gate cannot read its
        inputs from a sheet that exists: no recap sheet at all, recap columns
        unresolved (Gate 2), no tract sheets, or a tract sheet whose
        grantor/grantee columns are unresolved (Gate 3). Missing optional
        columns (interest-change, book/page) and absent OGL/WI sheets are
        warnings, not blocks.
        """
        topology = self._mapper.map(path)
        items: list[CoverageItem] = []
        blocking: list[str] = []
        warnings: list[str] = []

        # Gate 2 — recap.
        recap = self._extractor.recap_sheet(topology, path)
        if recap is None:
            blocking.append("No recap/summary sheet found — Gate 2 (Acreage Footing) cannot run.")
            items.append(CoverageItem(Gate.ACREAGE_FOOTING.value, "—", "sheet_absent", (), 0))
        else:
            fields = {"tract": self._column_map.tract, "gross_acres": self._column_map.gross_acres,
                      "interest_fraction": self._column_map.interest_fraction,
                      "net_acres": self._column_map.net_acres}
            resolved, rows = self._extractor.resolve_fields(path, recap, fields)
            missing = tuple(n for n, c in resolved.items() if c is None)
            status = "columns_unresolved" if missing else "mapped"
            items.append(CoverageItem(Gate.ACREAGE_FOOTING.value, recap.name, status, missing, rows))
            if missing:
                blocking.append(
                    f"Recap sheet '{recap.name}' is missing columns {list(missing)} — "
                    "Gate 2 cannot run.")

        # Gates 1/3/4 — tract sheets.
        tracts = topology.tracts()
        if not tracts:
            blocking.append("No tract sheets found — Gates 1, 3, 4 cannot run.")
        for tract in tracts:
            resolved, rows = self._extractor.resolve_fields(path, tract, {
                "grantor": self._column_map.grantor, "grantee": self._column_map.grantee,
                "interest_change": self._column_map.interest_change,
                "book": self._column_map.book, "page": self._column_map.page,
            })
            chain_missing = tuple(n for n in ("grantor", "grantee") if resolved[n] is None)
            status = "columns_unresolved" if chain_missing else "mapped"
            note_bits = []
            if resolved["interest_change"] is None:
                note_bits.append("no interest-change column (Gate 1 skipped)")
            if resolved["book"] is None or resolved["page"] is None:
                note_bits.append("no book/page columns (Gate 4 skipped)")
            items.append(CoverageItem(
                Gate.CHAIN_CONTINUITY.value, tract.name, status, chain_missing, rows,
                "; ".join(note_bits)))
            if chain_missing:
                blocking.append(
                    f"Tract sheet '{tract.name}' is missing {list(chain_missing)} — "
                    "Gate 3 (Chain Continuity) cannot run.")
            elif note_bits:
                warnings.append(f"{tract.name}: {'; '.join(note_bits)}.")

        # Gate 5 — OGL / WI (absent sheets are warnings, unresolved columns block).
        ogl_sheet = topology.ogl_register()
        if ogl_sheet is None:
            warnings.append("No OGL register sheet — Gate 5 (OGL Parity) will not run.")
        else:
            resolved, rows = self._extractor.resolve_fields(path, ogl_sheet, {
                "tract": self._column_map.tract, "royalty": self._column_map.royalty})
            missing = tuple(n for n, c in resolved.items() if c is None)
            items.append(CoverageItem(Gate.OGL_PARITY.value, ogl_sheet.name,
                         "columns_unresolved" if missing else "mapped", missing, rows))
            if missing:
                blocking.append(
                    f"OGL sheet '{ogl_sheet.name}' is missing columns {list(missing)} — "
                    "Gate 5 cannot run correctly.")
        if not topology.working_interest_sheets():
            warnings.append("No Working-Interest sheet — Gate 5 (OGL Parity) will not run.")

        return CoverageReport(tuple(items), tuple(blocking), tuple(warnings))

    @staticmethod
    def _enrich_footing(failures: Sequence[Failure], refs: _FootingRefs) -> list[Failure]:
        """Attach the exact cell + formula so the repairer can act
        deterministically without re-deriving the layout."""
        out: list[Failure] = []
        for f in failures:
            proof = dict(f.proof)
            proof.update({
                "sheet": refs.sheet,
                "cell": refs.net_cell,
                "formula": f"{refs.gross_cell}*{refs.fraction_cell}",
            })
            out.append(Failure(f.gate, f.category, f.reference, f.detail, proof))
        return out


# --------------------------------------------------------------------------- #
# Repairer implementation
# --------------------------------------------------------------------------- #

#: A recalc step operating in place on a freshly written version file.
RecalcFn = Callable[[Path], None]


class SurgeonRepairer:
    """Applies Category A repairs and writes the N+1 workbook.

    * XML_STATE_ERROR -> destroy the calc chain, force full recalc on load.
    * MATH_FOOTING_ERROR -> inject the pro-rata formula (carried in the failure
      proof) into the target cell.
    * METADATA_MISSING -> left to the loop's source-fetch step (no fabrication
      here); recorded but not silently altered.

    Never overwrites the old version. Then recalculates the new file so the
    next evaluation sees materialized values.
    """

    def __init__(self, recalc: Optional[RecalcFn] = None) -> None:
        self._archives = ArchiveManager()
        self._patcher = XMLPatcher()
        self._calc = CalcChainDestroyer()
        self._recalc = recalc or self._default_recalc

    def apply(self, failures, old_version, new_version) -> None:  # type: ignore[no-untyped-def]
        archive = self._archives.load(Path(old_version.file_path))

        if any(f.category == FailureCategory.XML_STATE_ERROR for f in failures):
            self._calc.destroy(archive)

        for f in failures:
            if f.category != FailureCategory.MATH_FOOTING_ERROR:
                continue
            sheet = f.proof.get("sheet")
            cell = f.proof.get("cell")
            formula = f.proof.get("formula")
            if not (sheet and cell and formula):
                continue  # cannot repair without a target; leave for review
            part = self._sheet_part(archive, sheet)
            if part is None:
                continue
            patched, _ = self._patcher.set_cell_formula(archive.read(part), cell, formula)
            archive.replace(part, patched)

        self._archives.save(archive, Path(new_version.file_path))
        self._recalc(Path(new_version.file_path))

    def _sheet_part(self, archive, title: str) -> Optional[str]:  # type: ignore[no-untyped-def]
        """Resolve a sheet title to its worksheet part via workbook.xml +
        rels."""
        if not archive.has("xl/workbook.xml") or not archive.has("xl/_rels/workbook.xml.rels"):
            return None
        wb = etree.fromstring(archive.read("xl/workbook.xml"))
        rid: Optional[str] = None
        for sheet in wb.iter(f"{{{_NS_MAIN}}}sheet"):
            if sheet.get("name") == title:
                rid = sheet.get(f"{{{_NS_R}}}id")
                break
        if rid is None:
            return None
        rels = etree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        for rel in rels:
            if rel.get("Id") == rid:
                return self._resolve_target(archive, rel.get("Target", ""))
        return None

    @staticmethod
    def _resolve_target(archive, target: str) -> Optional[str]:  # type: ignore[no-untyped-def]
        """Map a relationship Target to the actual part name. Targets may be
        written relative to xl/ ("worksheets/sheet1.xml"), already prefixed
        ("xl/worksheets/sheet1.xml"), absolute ("/xl/..."), or "../"-relative;
        resolve by checking which candidate actually exists in the archive."""
        raw = target.lstrip("/")
        candidates = [
            raw,
            "xl/" + raw,
            raw[3:] if raw.startswith("../") else "",
            "xl/" + raw[3:] if raw.startswith("../") else "",
        ]
        for cand in candidates:
            if cand and archive.has(cand):
                return cand
        return None

    def _default_recalc(self, path: Path) -> None:
        """Recalculate in place with LibreOffice if it functions; otherwise the
        injected formula stands with fullCalcOnLoad set and will evaluate when
        the workbook is next opened by a real engine."""
        engine = LibreOfficeEngine()
        if not engine.conversion_works():
            return
        result = engine.run_headless_recalc(path)
        # Replace the file with the recalculated copy so cached values persist.
        if result.recalculated_path != path and result.recalculated_path.exists():
            path.write_bytes(result.recalculated_path.read_bytes())


# --------------------------------------------------------------------------- #
# SourceProbe implementation
# --------------------------------------------------------------------------- #


class OKCountySourceProbe:
    """Gate-4 probe wiring the OKCounty client, verifier, and budget manager.

    A budget breach surfaces as ``found=False`` with a budget note so the Gate-4
    validator escalates it; the loop then opens a BUDGET_CAP_REACHED escalation.
    Nothing is fabricated — an unreachable or over-budget source is reported as
    unverified, never assumed.
    """

    def __init__(self, client, verifier, budget) -> None:  # type: ignore[no-untyped-def]
        self._client = client
        self._verifier = verifier
        self._budget = budget

    def verify(self, line: InstrumentLine) -> SourceProbeResult:
        from ..api.okcounty import BudgetCapReached, OKCountyError

        try:
            resp = self._client.execute(
                "documents/search", {"book": line.book, "page": line.page})
        except OKCountyError as exc:
            return SourceProbeResult(found=False, free_to_view=False, detail=str(exc))

        if resp.status_code == 404:
            return SourceProbeResult(found=False, free_to_view=False, detail="404 Not Found")

        flag = self._verifier.evaluate_free_flag(resp.json)
        if not flag.found:
            return SourceProbeResult(found=False, free_to_view=False, detail=flag.detail)

        if not flag.free_to_view:
            try:
                self._budget.track_spend(flag.estimated_cost,
                                         f"Book {line.book}/Page {line.page}")
            except BudgetCapReached as exc:
                return SourceProbeResult(found=False, free_to_view=False, detail=str(exc))

        return SourceProbeResult(found=True, free_to_view=flag.free_to_view, detail=flag.detail)
