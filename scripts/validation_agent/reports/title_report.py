"""TitleReportGenerator -- the examiner-facing title report.

Produces the substantive deliverable a landman/examiner wants from a runsheet
workbook:

    * a chronological CHAIN OF TITLE (every instrument, parties, book/page or
      instrument #, legal, and runsheet notes),
    * a chained-out INTEREST LEDGER computed with exact rational math -- walking
      each conveyance to a current net-mineral-ownership table that reconciles
      to 100%,
    * an OGL REGISTER TIE-OUT keyed by OGL number (lessor/lessee/depth, which
      tracts reference it, and whether it ties to the WI sheets), and
    * the LEGAL DESCRIPTIONS in play, plus any open flags from validation.

Golden Law: nothing here is invented. Every figure traces to a workbook cell;
where a fact is missing (an unrecorded reservation, an untraceable grantor) the
report says so explicitly instead of guessing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Optional

from ..ingestion.manifest_builder import WorkbookManifest
from ..ingestion.sheet_classifier import SheetCategory
from ..models import Finding
from ..validators._helpers import (data_cells_in_column, find_header_column,
                                   is_total_row, parse_fraction)

# Grantor names that denote the sovereign / root of title (no prior vesting).
_SOVEREIGN = {"US PATENT", "USA", "UNITED STATES", "UNITED STATES OF AMERICA",
              "PATENT", "STATE OF OKLAHOMA", "STATE", "SOVEREIGN"}


@dataclass
class ChainLink:
    order: int
    sheet: str
    row: int
    instrument_type: str
    date: str
    grantor: str
    grantee: str
    conveyed: Optional[Fraction]
    retained: Optional[Fraction]
    source_ref: str
    legal: str
    note: str


@dataclass
class ChainResult:
    links: list[ChainLink] = field(default_factory=list)
    ownership: dict[str, Fraction] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_owned(self) -> Fraction:
        total = Fraction(0)
        for v in self.ownership.values():
            total += v
        return total


class TitleReportGenerator:
    def generate(self, manifest: WorkbookManifest, out_dir: Path,
                 findings: Optional[list[Finding]] = None,
                 *, prospect: str = "") -> dict[str, str]:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        chain = self._chain_out(manifest)
        ogl = self._ogl_tieout(manifest)
        legals = self._legals(manifest)

        md_path = out_dir / "title_report.md"
        md_path.write_text(self._render_md(manifest, chain, ogl, legals,
                                           findings or [], prospect),
                           encoding="utf-8")
        json_path = out_dir / "title_report.json"
        json_path.write_text(json.dumps(self._render_json(manifest, chain, ogl,
                                                          legals), indent=2,
                                        default=str), encoding="utf-8")
        return {"title_report_md": str(md_path), "title_report_json": str(json_path)}

    # -- interest chain-out -------------------------------------------------
    def _chain_out(self, manifest: WorkbookManifest) -> ChainResult:
        result = ChainResult()
        runsheets = manifest.by_category(SheetCategory.RUNSHEET)
        order = 0
        for sheet in runsheets:
            g_col = find_header_column(sheet, "grantor")
            e_col = find_header_column(sheet, "grantee")
            c_col = find_header_column(sheet, "conveyed", "conveyance", "granted")
            r_col = find_header_column(sheet, "retained", "reserved", "reservation")
            gi_col = find_header_column(sheet, "grantor interest", "grantor int")
            t_col = find_header_column(sheet, "instrument type", "type")
            d_col = find_header_column(sheet, "date", "recording date",
                                       "instrument date")
            legal_col = find_header_column(sheet, "legal description", "legal",
                                           "description")
            note_col = find_header_column(sheet, "note", "notes", "remarks",
                                          "comment")
            book_col = find_header_column(sheet, "book")
            page_col = find_header_column(sheet, "page")
            inst_col = find_header_column(sheet, "instrument number", "inst #",
                                          "instrument #", "instrument no")
            if not (g_col and e_col):
                result.warnings.append(
                    f"{sheet.name}: no grantor/grantee columns; chain not built.")
                continue

            for gcell in data_cells_in_column(sheet, g_col):
                row = gcell.row
                if is_total_row(sheet, row) or gcell.value is None:
                    continue
                order += 1
                grantor = str(gcell.value).strip()
                grantee = self._txt(sheet, e_col, row)
                conveyed = parse_fraction(self._txt(sheet, c_col, row)) if c_col else None
                retained = parse_fraction(self._txt(sheet, r_col, row)) if r_col else None
                book, page = self._txt(sheet, book_col, row), self._txt(sheet, page_col, row)
                inst = self._txt(sheet, inst_col, row)
                source_ref = (f"Book {book}/Page {page}" if book and page
                              else (f"Inst #{inst}" if inst else "(no source)"))
                link = ChainLink(
                    order=order, sheet=sheet.name, row=row,
                    instrument_type=self._txt(sheet, t_col, row),
                    date=self._txt(sheet, d_col, row),
                    grantor=grantor, grantee=grantee,
                    conveyed=conveyed, retained=retained,
                    source_ref=source_ref,
                    legal=self._txt(sheet, legal_col, row),
                    note=self._txt(sheet, note_col, row))
                result.links.append(link)
                self._apply_link(result, link, order, gi_col, sheet, row)

        # Drop zeroed-out parties for a clean current-ownership view.
        result.ownership = {k: v for k, v in result.ownership.items() if v != 0}
        return result

    def _apply_link(self, result: ChainResult, link: ChainLink, order: int,
                    gi_col, sheet, row) -> None:
        """Move interest per one conveyance using exact fractions."""
        grantor_key = link.grantor.upper()
        grantee_key = link.grantee.upper()
        conveyed = link.conveyed
        if conveyed is None:
            result.warnings.append(
                f"Link {order} ({link.grantor}->{link.grantee}): conveyed interest "
                f"unparseable; ledger not advanced for this row.")
            return

        is_root = grantor_key in _SOVEREIGN or (order == 1
                                                and grantor_key not in result.ownership)
        if is_root:
            # Root of title: the sovereign/patent vests the grantee; the grantor
            # is not tracked as an owner.
            if grantor_key not in _SOVEREIGN:
                # First grantor may hold a stated "grantor interest"; seed it.
                seed = parse_fraction(self._txt(sheet, gi_col, row)) if gi_col else None
                result.ownership[grantor_key] = (seed if seed is not None
                                                 else Fraction(1))
                prev = result.ownership[grantor_key]
                result.ownership[grantee_key] = result.ownership.get(grantee_key, Fraction(0)) + conveyed
                result.ownership[grantor_key] = prev - conveyed
            else:
                result.ownership[grantee_key] = result.ownership.get(grantee_key, Fraction(0)) + conveyed
            return

        prev = result.ownership.get(grantor_key)
        if prev is None:
            result.warnings.append(
                f"Link {order}: grantor '{link.grantor}' is not previously vested; "
                f"interest cannot be traced (chain gap -- examiner review).")
            # Still credit the grantee with what the instrument purports to convey,
            # but flag the deficit rather than invent the grantor's holding.
            result.ownership[grantee_key] = result.ownership.get(grantee_key, Fraction(0)) + conveyed
            result.ownership[grantor_key] = -conveyed  # negative signals the gap
            return

        result.ownership[grantee_key] = result.ownership.get(grantee_key, Fraction(0)) + conveyed
        result.ownership[grantor_key] = prev - conveyed

    # -- OGL tie-out --------------------------------------------------------
    def _ogl_tieout(self, manifest: WorkbookManifest) -> list[dict]:
        registers = manifest.by_category(SheetCategory.OGL_REGISTER)
        tracts = manifest.by_category(SheetCategory.TRACT)
        wi_sheets = manifest.by_category(SheetCategory.WORKING_INTEREST)
        referenced = self._collect_lease_locs(tracts)
        in_wi = set(self._collect_lease_locs(wi_sheets).keys())

        out: list[dict] = []
        for sheet in registers:
            id_col = find_header_column(sheet, "ogl", "lease number", "lease id",
                                        "lease")
            lessor_col = find_header_column(sheet, "lessor")
            lessee_col = find_header_column(sheet, "lessee")
            depth_col = find_header_column(sheet, "depth", "interval", "formation",
                                           "limitation")
            book_col = find_header_column(sheet, "book")
            page_col = find_header_column(sheet, "page")
            if not id_col:
                continue
            for cell in data_cells_in_column(sheet, id_col):
                if is_total_row(sheet, cell.row) or cell.value is None:
                    continue
                lease = str(cell.value).strip()
                key = lease.upper().replace(" ", "")
                tracts_ref = sorted({loc for k, loc in referenced.items() if k == key})
                out.append({
                    "ogl_number": lease,
                    "lessor": self._txt(sheet, lessor_col, cell.row),
                    "lessee": self._txt(sheet, lessee_col, cell.row),
                    "depth": self._txt(sheet, depth_col, cell.row),
                    "source": self._source_ref(sheet, book_col, page_col, cell.row),
                    "referenced_in_tracts": tracts_ref,
                    "in_working_interest": key in in_wi,
                    "tie_status": ("tied" if (tracts_ref and key in in_wi)
                                   else "not referenced in tracts" if not tracts_ref
                                   else "missing from WI"),
                })
        return out

    def _collect_lease_locs(self, sheets) -> dict[str, str]:
        out: dict[str, str] = {}
        for sheet in sheets:
            col = find_header_column(sheet, "ogl", "lease number", "lease id", "lease")
            if not col:
                continue
            for cell in data_cells_in_column(sheet, col):
                if is_total_row(sheet, cell.row) or cell.value is None:
                    continue
                key = str(cell.value).upper().replace(" ", "")
                out.setdefault(key, sheet.name)
        return out

    # -- legals -------------------------------------------------------------
    def _legals(self, manifest: WorkbookManifest) -> list[dict]:
        seen: dict[str, dict] = {}
        for sheet in manifest.sheets:
            legal_col = find_header_column(sheet, "legal description", "legal",
                                           "description")
            if not legal_col:
                continue
            label_col = find_header_column(sheet, "tract", "parcel") or "A"
            for cell in data_cells_in_column(sheet, legal_col):
                if is_total_row(sheet, cell.row) or cell.value is None:
                    continue
                legal = str(cell.value).strip()
                if not legal or legal.lower() in ("legal description", "legal"):
                    continue
                if legal not in seen:
                    seen[legal] = {"legal": legal, "sheet": sheet.name,
                                   "label": self._txt(sheet, label_col, cell.row)}
        return list(seen.values())

    # -- rendering ----------------------------------------------------------
    def _render_md(self, manifest, chain: ChainResult, ogl, legals, findings,
                   prospect) -> str:
        L: list[str] = []
        title = f"Title Report{' -- ' + prospect if prospect else ''}"
        L.append(f"# {title}")
        L.append("")
        L.append(f"- Source workbook: `{manifest.path.name}`")
        L.append(f"- SHA-256: `{manifest.sha256}`")
        L.append(f"- Sheets: {len(manifest.sheets)} | "
                 f"tracts: {len(manifest.by_category(SheetCategory.TRACT))}")
        L.append("")
        L.append("> Automated title analysis. No legal or title fact is fabricated; "
                 "gaps are flagged for examiner determination.")
        L.append("")

        # Chain of title
        L.append("## 1. Chain of Title")
        L.append("")
        if not chain.links:
            L.append("_No runsheet chain could be built (missing grantor/grantee "
                     "columns)._")
        else:
            L.append("| # | Instrument | Date | Grantor | Grantee | Conveyed | "
                     "Retained | Source | Legal | Notes |")
            L.append("|---|-----------|------|---------|---------|----------|"
                     "----------|--------|-------|-------|")
            for k in chain.links:
                L.append("| {o} | {t} | {d} | {gr} | {ge} | {c} | {r} | {s} | {lg} | {n} |"
                         .format(o=k.order, t=self._esc(k.instrument_type),
                                 d=self._esc(k.date), gr=self._esc(k.grantor),
                                 ge=self._esc(k.grantee),
                                 c=self._frac(k.conveyed), r=self._frac(k.retained),
                                 s=self._esc(k.source_ref), lg=self._esc(k.legal),
                                 n=self._esc(k.note)))
        L.append("")

        # Interest ledger
        L.append("## 2. Chained-Out Interest (current net mineral ownership)")
        L.append("")
        if chain.ownership:
            L.append("| Owner | Interest | Decimal | Percent |")
            L.append("|-------|----------|---------|---------|")
            for owner, frac in sorted(chain.ownership.items(),
                                      key=lambda kv: (-float(kv[1]), kv[0])):
                L.append(f"| {self._esc(owner)} | {self._frac(frac)} | "
                         f"{float(frac):.6f} | {float(frac) * 100:.4f}% |")
            total = chain.total_owned
            recon = "reconciles to 100%" if total == 1 else \
                f"**does NOT reconcile** (sums to {self._frac(total)} = {float(total):.6f})"
            L.append("")
            L.append(f"- Ownership {recon}.")
        else:
            L.append("_No interest could be chained out._")
        if chain.warnings:
            L.append("")
            L.append("**Chain warnings (examiner review):**")
            for w in chain.warnings:
                L.append(f"- {w}")
        L.append("")

        # OGL tie-out
        L.append("## 3. OGL Register Tie-Out")
        L.append("")
        if ogl:
            L.append("| OGL # | Lessor | Lessee | Depth | Source | Tracts | In WI | Tie |")
            L.append("|-------|--------|--------|-------|--------|--------|-------|-----|")
            for o in ogl:
                L.append("| {n} | {lr} | {le} | {dp} | {s} | {tr} | {wi} | {tie} |"
                         .format(n=self._esc(o["ogl_number"]),
                                 lr=self._esc(o["lessor"]), le=self._esc(o["lessee"]),
                                 dp=self._esc(o["depth"]), s=self._esc(o["source"]),
                                 tr=self._esc(", ".join(o["referenced_in_tracts"]) or "-"),
                                 wi="yes" if o["in_working_interest"] else "no",
                                 tie=self._esc(o["tie_status"])))
        else:
            L.append("_No OGL register rows found._")
        L.append("")

        # Legals
        L.append("## 4. Legal Descriptions")
        L.append("")
        if legals:
            for lg in legals:
                label = f" ({lg['label']})" if lg["label"] else ""
                L.append(f"- **{self._esc(lg['legal'])}**{label} "
                         f"[{self._esc(lg['sheet'])}]")
        else:
            L.append("_No legal descriptions found in the workbook._")
        L.append("")

        # Flags
        L.append("## 5. Open Flags")
        L.append("")
        flags = [f for f in findings if f.escalate]
        if flags:
            for f in flags:
                loc = f" @ {f.location}" if f.location else ""
                L.append(f"- [{f.severity.value}] {f.gate_name}: {f.message}{loc}")
        else:
            L.append("_No open flags recorded for this pass._")
        L.append("")
        return "\n".join(L)

    def _render_json(self, manifest, chain: ChainResult, ogl, legals) -> dict:
        return {
            "source": manifest.path.name,
            "sha256": manifest.sha256,
            "chain": [{
                "order": k.order, "instrument_type": k.instrument_type,
                "date": k.date, "grantor": k.grantor, "grantee": k.grantee,
                "conveyed": self._frac(k.conveyed), "retained": self._frac(k.retained),
                "source": k.source_ref, "legal": k.legal, "note": k.note,
            } for k in chain.links],
            "ownership": {o: self._frac(v) for o, v in chain.ownership.items()},
            "ownership_reconciles": chain.total_owned == 1,
            "ogl_tieout": ogl,
            "legals": legals,
            "warnings": chain.warnings,
        }

    # -- small helpers ------------------------------------------------------
    @staticmethod
    def _txt(sheet, col, row) -> str:
        if not col:
            return ""
        cell = sheet.cell(f"{col}{row}")
        return str(cell.value).strip() if cell and cell.value is not None else ""

    @classmethod
    def _source_ref(cls, sheet, book_col, page_col, row) -> str:
        book, page = cls._txt(sheet, book_col, row), cls._txt(sheet, page_col, row)
        return f"Book {book}/Page {page}" if book and page else ""

    @staticmethod
    def _frac(value: Optional[Fraction]) -> str:
        if value is None:
            return "-"
        if value.denominator == 1:
            return str(value.numerator)
        return f"{value.numerator}/{value.denominator}"

    @staticmethod
    def _esc(text: str) -> str:
        return str(text).replace("|", "\\|").replace("\n", " ")
