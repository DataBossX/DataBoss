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
        findings = findings or []
        chain = self._chain_out(manifest)
        ogl = self._ogl_tieout(manifest)
        legals = self._legals(manifest)
        net_acres = self._total_net_acres(manifest)
        exceptions = self._exceptions(manifest)
        completeness = self._completeness(chain, ogl, findings)

        md_path = out_dir / "title_report.md"
        md_path.write_text(self._render_md(manifest, chain, ogl, legals, net_acres,
                                           exceptions, completeness, findings,
                                           prospect),
                           encoding="utf-8")
        json_path = out_dir / "title_report.json"
        json_path.write_text(json.dumps(
            self._render_json(manifest, chain, ogl, legals, net_acres, exceptions,
                              completeness), indent=2, default=str),
            encoding="utf-8")
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

        if not grantee_key:
            result.warnings.append(
                f"Link {order}: grantee is blank; interest not moved (would create "
                f"a phantom owner).")
            return
        if grantor_key == grantee_key:
            result.warnings.append(
                f"Link {order}: grantor and grantee are the same party "
                f"({link.grantor}); treated as a correction -- no interest moved.")
            return

        prev_grantor = result.ownership.get(grantor_key)
        conveyed = link.conveyed
        if conveyed is None:
            # A deed may state only what is RESERVED; then the grantor conveys
            # everything they held except the reservation.
            if link.retained is not None and prev_grantor is not None:
                conveyed = prev_grantor - link.retained
            else:
                result.warnings.append(
                    f"Link {order} ({link.grantor}->{link.grantee}): conveyed "
                    f"interest could not be determined; ledger not advanced.")
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
        referenced = self._collect_lease_refs(tracts)
        in_wi = set(self._collect_lease_refs(wi_sheets).keys())

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
                tracts_ref = sorted(set(referenced.get(key, [])))
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

    def _collect_lease_refs(self, sheets) -> dict[str, list[str]]:
        """Map each OGL key to every tract label that references it (a lease may
        be referenced from several tract rows/sheets)."""
        out: dict[str, list[str]] = {}
        for sheet in sheets:
            col = find_header_column(sheet, "ogl", "lease number", "lease id", "lease")
            if not col:
                continue
            label_col = find_header_column(sheet, "tract", "parcel")
            for cell in data_cells_in_column(sheet, col):
                if is_total_row(sheet, cell.row) or cell.value is None:
                    continue
                key = str(cell.value).upper().replace(" ", "")
                label = self._txt(sheet, label_col, cell.row) if label_col else ""
                label = (f"{sheet.name}: {label}" if label else sheet.name)
                out.setdefault(key, [])
                if label not in out[key]:
                    out[key].append(label)
        return out

    # -- net mineral acres --------------------------------------------------
    def _total_net_acres(self, manifest: WorkbookManifest) -> Optional[float]:
        """Foot the tract net acres (preferring a summary tab) for NMA math."""
        from ..validators._helpers import numeric
        from ..validators.val_acreage import AcreageValidator
        tracts = manifest.by_category(SheetCategory.TRACT)
        if not tracts:
            return None
        total = 0.0
        found = False
        for sheet in AcreageValidator._acreage_sheets(tracts):
            col = AcreageValidator._acre_col(sheet)
            if not col:
                continue
            for cell in data_cells_in_column(sheet, col):
                if is_total_row(sheet, cell.row):
                    continue
                v = numeric(cell.value)
                if v is not None:
                    total += v
                    found = True
        return round(total, 4) if found else None

    # -- curative requirements / exceptions ---------------------------------
    def _exceptions(self, manifest: WorkbookManifest) -> list[dict]:
        out: list[dict] = []
        for sheet in manifest.by_category(SheetCategory.EXCEPTION_CURATIVE):
            hdr = sheet.header_row
            for r in range(hdr + 1, sheet.max_row + 1):
                if is_total_row(sheet, r):
                    continue
                cells = [c for c in sheet.cells.values()
                         if c.row == r and c.value is not None]
                if not cells:
                    continue
                text = " | ".join(str(c.value).strip()
                                  for c in sorted(cells, key=lambda c: c.coord))
                out.append({"sheet": sheet.name, "row": r, "text": text})
        return out

    # -- report completeness (the honest "how perfect is it?") --------------
    def _completeness(self, chain: ChainResult, ogl: list[dict],
                      findings: list[Finding]) -> tuple[list[tuple[str, bool]], int, int]:
        checks: list[tuple[str, bool]] = []
        checks.append(("Interest chains out and reconciles to 100%",
                       bool(chain.ownership) and chain.total_owned == 1))
        checks.append(("Every chain link has a recorded source",
                       bool(chain.links) and all(
                           k.source_ref != "(no source)" for k in chain.links)))
        checks.append(("No unresolved chain gaps", not chain.warnings))
        checks.append(("Every OGL ties to tracts and WI",
                       all(o["tie_status"] == "tied" for o in ogl) if ogl else True))
        checks.append(("No open escalation flags",
                       not any(f.escalate for f in findings)))
        passed = sum(1 for _, ok in checks if ok)
        return checks, passed, len(checks)

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
    def _render_md(self, manifest, chain: ChainResult, ogl, legals, net_acres,
                   exceptions, completeness, findings, prospect) -> str:
        checks, passed, total_checks = completeness
        L: list[str] = []
        title = f"Title Report{' -- ' + prospect if prospect else ''}"
        L.append(f"# {title}")
        L.append("")
        L.append(f"- Source workbook: `{manifest.path.name}`")
        L.append(f"- SHA-256: `{manifest.sha256}`")
        L.append(f"- Sheets: {len(manifest.sheets)} | "
                 f"tracts: {len(manifest.by_category(SheetCategory.TRACT))}"
                 + (f" | net acres: {net_acres}" if net_acres is not None else ""))
        pct = round(100 * passed / total_checks) if total_checks else 0
        L.append(f"- **Report completeness: {passed}/{total_checks} ({pct}%)**")
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
            nma_hdr = " Net Acres |" if net_acres is not None else ""
            nma_sep = "-----------|" if net_acres is not None else ""
            L.append(f"| Owner | Interest | Decimal | Percent |{nma_hdr}")
            L.append(f"|-------|----------|---------|---------|{nma_sep}")
            for owner, frac in sorted(chain.ownership.items(),
                                      key=lambda kv: (-float(kv[1]), kv[0])):
                nma = (f" {float(frac) * net_acres:.4f} |"
                       if net_acres is not None else "")
                L.append(f"| {self._esc(owner)} | {self._frac(frac)} | "
                         f"{float(frac):.6f} | {float(frac) * 100:.4f}% |{nma}")
            if net_acres is not None:
                L.append("")
                L.append(f"- Net mineral acres computed against a footed "
                         f"{net_acres} gross tract acres.")
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

        # Curative requirements / exceptions
        L.append("## 5. Curative Requirements & Exceptions")
        L.append("")
        if exceptions:
            for e in exceptions:
                L.append(f"- {self._esc(e['text'])} [{self._esc(e['sheet'])} "
                         f"row {e['row']}]")
        else:
            L.append("_No exception/curative sheet rows found._")
        L.append("")

        # Report completeness
        L.append("## 6. Report Completeness")
        L.append("")
        L.append(f"**{passed}/{total_checks} checks passed ({pct}%).** A report "
                 f"is examiner-ready when every check passes; a failing check is "
                 f"work the automation could not complete without a human "
                 f"determination.")
        L.append("")
        for label, ok in checks:
            L.append(f"- [{'x' if ok else ' '}] {label}")
        L.append("")

        # Flags
        L.append("## 7. Open Flags")
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

    def _render_json(self, manifest, chain: ChainResult, ogl, legals, net_acres,
                     exceptions, completeness) -> dict:
        checks, passed, total_checks = completeness
        return {
            "source": manifest.path.name,
            "sha256": manifest.sha256,
            "net_acres": net_acres,
            "chain": [{
                "order": k.order, "instrument_type": k.instrument_type,
                "date": k.date, "grantor": k.grantor, "grantee": k.grantee,
                "conveyed": self._frac(k.conveyed), "retained": self._frac(k.retained),
                "source": k.source_ref, "legal": k.legal, "note": k.note,
            } for k in chain.links],
            "ownership": {o: self._frac(v) for o, v in chain.ownership.items()},
            "ownership_net_acres": (
                {o: round(float(v) * net_acres, 4) for o, v in chain.ownership.items()}
                if net_acres is not None else {}),
            "ownership_reconciles": chain.total_owned == 1,
            "ogl_tieout": ogl,
            "legals": legals,
            "exceptions": exceptions,
            "completeness": {"passed": passed, "total": total_checks,
                             "checks": {label: ok for label, ok in checks}},
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
