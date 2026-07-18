"""Title intelligence: the connective tissue of the DataBossX landman system.

This module wires the three previously-disconnected engines together into one
coherent title-examination workflow:

* ``grocery_report_pipeline`` -- deterministic document intelligence: classify a
  document and extract structured facts (grantor/grantee, legal description,
  instrument number, gross acres, dates) with **no fabrication**.
* ``horizon`` -- exact fraction/decimal interest math, instrument chaining,
  chain-of-title continuity checks, over-conveyance detection, and the
  golden-source validation gate.
* the DataBossX foundation (:mod:`databossx`) -- the durable project/evidence
  spine: content-addressed asset vault, per-project SQLite, ``derived_artifacts``
  lineage, and the append-only ``audit_events`` log.

The result is a landman helper that turns a pile of uploaded title documents into
a reconciled chain of title, a current-ownership ledger with net mineral acres,
and an examiner worklist -- persisted as an auditable derived artifact. Where the
files do not support a determination (unknown starting interest, an
over-conveyance, or a chain-of-title break), the tract is flagged
``Needs Examiner Review`` rather than balanced by invention.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .config import DataBossConfig
from .database import DataBossDatabase
from .hashing import copy_file_to_vault

# The exact-math (horizon) and document-intelligence (grocery) engines live at
# the repository root; make them importable regardless of the process CWD.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import grocery_report_pipeline as _grp  # noqa: E402  (document intelligence)
from horizon.artifacts import write_review_worklist  # noqa: E402
from horizon.chaining import OGLRecord, RunsheetNote, reconcile_chain  # noqa: E402
from horizon.interest import (  # noqa: E402
    FULL,
    format_acres,
    format_fraction,
    net_acres,
    try_parse_acres,
    try_parse_interest,
)
from horizon.models import ReportModel, TitleRow  # noqa: E402
from horizon.pipeline import chain_to_report  # noqa: E402
from horizon.report_io import write_report  # noqa: E402
from horizon.validation import Requirements, validate_report  # noqa: E402

RECIPE_VERSION = "title_intelligence/1.0.0"

# Document categories (from the grocery classifier) that actually convey a
# mineral ownership interest and therefore participate in the interest chain.
_CONVEYANCE_CATEGORIES = {"deed", "assignment"}

# Human-friendly instrument sub-types, most specific first.
_DOC_SUBTYPES: List[Tuple[str, str]] = [
    ("Mineral Deed", r"mineral\s+deed"),
    ("Royalty Deed", r"royalty\s+deed"),
    ("Warranty Deed", r"warranty\s+deed"),
    ("Quitclaim Deed", r"qu[ck]?laim\s+deed|quitclaim\s+deed"),
    ("Special Warranty Deed", r"special\s+warranty\s+deed"),
    ("Assignment of OGL", r"assignment\s+of\s+(?:oil|lease|overriding)"),
    ("Oil & Gas Lease", r"oil\s*(?:&|and)\s*gas\s+lease"),
    ("Probate / Estate", r"probate|last\s+will|estate\s+of|letters\s+testamentary"),
    ("Affidavit", r"affidavit"),
]

# Conveyed mineral interest, e.g. "an undivided 1/2 interest", "undivided 12.5%",
# "an undivided one-half (1/2) interest" (parenthetical numeric form).
_UNDIVIDED_RX = re.compile(
    r"undivided\s+(?:[a-z\- ]{0,20}?\()?\s*(\d+\s*/\s*\d+|\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?)\s*"
    r"\)?\s*(?:interest|mineral|royalty|of|in\b)",
    re.I,
)
# Fallback: "conveys ... 1/2" / "grants ... 12.5%".
_CONVEY_RX = re.compile(
    r"(?:convey|grant|assign|transfer|sell)s?\b[^.\n]{0,90}?"
    r"(\d+\s*/\s*\d+|\d+(?:\.\d+)?\s*%)",
    re.I,
)

# Public-land-survey legal description, tolerant of both abbreviated
# ("Section 20, T9N, R22W") and spelled-out ("Section 20, Township 9 North,
# Range 22 West") and hyphenated ("Sec. 20, T-9-N, R-22-W") real-deed forms.
# Normalized to a single canonical string so all forms group to one tract.
_LEGAL_STRUCT_RX = re.compile(
    r"sec(?:tion)?\.?\s*(\d+[A-Za-z]?)\s*[, ]+\s*"
    r"t(?:wp|ownship)?\.?\s*-?\s*(\d+)\s*-?\s*(n(?:orth)?|s(?:outh)?)\b\s*[, ]*\s*"
    r"r(?:ge|ange)?\.?\s*-?\s*(\d+)\s*-?\s*(e(?:ast)?|w(?:est)?)\b",
    re.I,
)


def _extract_legal(text: str) -> str:
    """Extract and normalize a PLSS legal description, or "" when none parses.

    Handles common real-deed spellings; never guesses. OCR that mangles a digit
    into a letter (e.g. "T9N" -> "TON") simply fails to match and the field is
    left blank for examiner review rather than fabricated.
    """
    m = _LEGAL_STRUCT_RX.search(text)
    if m:
        sec, twp, twd, rng, rwd = m.groups()
        return f"Section {sec}, T{twp}{twd[0].upper()}, R{rng}{rwd[0].upper()}"
    m2 = _grp._LEGAL_RX.search(text)
    if m2:
        return _grp.norm_ws(m2.group(0))
    return ""


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tract_key(legal: str) -> str:
    """Normalized tract key (mirrors horizon.pipeline._tract_key)."""
    return re.sub(r"[^A-Za-z0-9]+", "", str(legal or "")).upper()


# ---------------------------------------------------------------------------
# Document -> conveyance fact extraction (deterministic; no fabrication)
# ---------------------------------------------------------------------------
@dataclass
class ConveyanceFact:
    """One title document reduced to the fields the chain engine needs."""

    filename: str = ""
    doc_type: str = ""
    categories: List[str] = field(default_factory=list)
    grantor: str = ""
    grantee: str = ""
    conveyed_interest: str = ""
    legal_description: str = ""
    instrument_number: str = ""
    instrument_date: str = ""
    gross_acres: str = ""
    county: str = ""
    state: str = ""
    is_conveyance: bool = False
    ocr_used: bool = False
    confidence: float = 0.0
    review_flags: List[str] = field(default_factory=list)
    snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _classify(name: str, text: str) -> List[str]:
    """Reuse the grocery classifier's rule set on an in-memory string."""
    hay = f"{name}\n{text}".lower()
    labels: List[Tuple[str, int]] = []
    for label, patterns in _grp.CLASSIFY_RULES:
        hits = sum(1 for pat in patterns if re.search(pat, hay))
        if hits:
            labels.append((label, hits))
    labels.sort(key=lambda x: -x[1])
    return [label for label, _ in labels]


def _doc_subtype(text: str, categories: List[str]) -> str:
    low = text.lower()
    for label, pat in _DOC_SUBTYPES:
        if re.search(pat, low):
            return label
    if categories:
        return categories[0].title()
    return "Unknown / Review Required"


def _extract_conveyed_interest(text: str) -> str:
    """Extract the conveyed mineral interest as a normalized fraction string.

    Returns "" when no interest can be parsed exactly (never guesses)."""
    for rx in (_UNDIVIDED_RX, _CONVEY_RX):
        m = rx.search(text)
        if not m:
            continue
        raw = re.sub(r"\s+", "", m.group(1))
        frac = try_parse_interest(raw)
        if frac is not None:
            return format_fraction(frac)
    return ""


def _extract_instrument(text: str) -> str:
    m = _grp._INSTR_RX.search(text)
    if not m:
        return ""
    book, page, instr = m.group(1), m.group(2), m.group(3)
    if book and page:
        return f"Book {book} Page {page}"
    if instr:
        return instr
    return ""


def extract_conveyance(filename: str, text: str) -> ConveyanceFact:
    """Turn one document's text into a :class:`ConveyanceFact`.

    Uses the grocery pipeline's deterministic classifier + regex fact extractors
    plus an exact-interest parser (horizon). Every high-value field that cannot
    be found is left blank and recorded in ``review_flags`` -- the engine never
    invents grantor/grantee/interest/legal data.
    """
    text = text or ""
    fact = ConveyanceFact(filename=filename)
    fact.categories = _classify(filename, text)
    fact.doc_type = _doc_subtype(text, fact.categories)

    fact.grantor = _grp._capture_party(text, ["grantor", "assignor", "lessor"]) or ""
    fact.grantee = _grp._capture_party(text, ["grantee", "assignee", "lessee"]) or ""
    fact.conveyed_interest = _extract_conveyed_interest(text)
    fact.legal_description = _extract_legal(text)

    gross = _grp._GROSS_RX.search(text)
    fact.gross_acres = gross.group(1).replace(",", "") if gross else ""

    fact.instrument_number = _extract_instrument(text)
    fact.instrument_date = _grp.parse_date(text) or ""

    county = _grp._COUNTY_RX.search(text)
    fact.county = county.group(1) if county else ""
    state = _grp._STATE_RX.search(text)
    fact.state = state.group(1) if state else ""

    fact.snippet = _grp.norm_ws(text)[:200]

    is_ownership_doc = any(c in _CONVEYANCE_CATEGORIES for c in fact.categories)
    fact.is_conveyance = bool(is_ownership_doc and fact.conveyed_interest)

    # Review flags + a simple confidence score for the examiner worklist.
    weights = {
        "grantor": 0.25,
        "grantee": 0.25,
        "conveyed_interest": 0.30,
        "legal_description": 0.20,
    }
    score = 0.0
    for fieldname, weight in weights.items():
        if getattr(fact, fieldname):
            score += weight
        elif is_ownership_doc:
            fact.review_flags.append(f"missing {fieldname.replace('_', ' ')}")
    fact.confidence = round(score, 2)
    if is_ownership_doc and not fact.is_conveyance:
        fact.review_flags.append("conveyed interest not determinable from document")
    return fact


# ---------------------------------------------------------------------------
# Conveyances -> reconciled chain of title + ownership ledger + validation
# ---------------------------------------------------------------------------
def _ownership_ledger(
    conveyances: Sequence[ConveyanceFact],
) -> List[Dict[str, Any]]:
    """Per-tract current-ownership ledger built from exact chain reconciliation.

    The "current mineral owner" is the last grantee whose link ties out cleanly;
    once the chain breaks (over-conveyance / continuity / legal-tie failure) the
    holder is poisoned and ownership is reported as undetermined -- pending
    examiner review -- rather than fabricated.
    """
    tracts: Dict[str, List[ConveyanceFact]] = {}
    order: List[str] = []
    for f in conveyances:
        key = _tract_key(f.legal_description) or "UNSPECIFIED"
        if key not in tracts:
            tracts[key] = []
            order.append(key)
        tracts[key].append(f)

    ledger: List[Dict[str, Any]] = []
    for key in order:
        recs = tracts[key]
        tract_legal = recs[0].legal_description or key
        ogl = [
            OGLRecord(
                instrument_number=f.instrument_number,
                grantor=f.grantor,
                grantee=f.grantee,
                conveyed_interest=f.conveyed_interest,
                legal_description=f.legal_description,
                doc_type=f.doc_type,
                instrument_date=f.instrument_date,
                gross_acres=f.gross_acres,
            )
            for f in recs
        ]
        result = reconcile_chain(key, ogl, starting_interest=FULL, tract_legal=tract_legal)

        # Walk to the last cleanly-balanced, tied link to name the current owner.
        current_owner = ""
        current_interest: Optional[Fraction] = None
        for link in result.links:
            if (
                link.reconciliation.status == "balanced"
                and link.tied_to_legal
                and link.grantor_continuity
                and link.holder_after is not None
            ):
                current_owner = link.grantee
                current_interest = link.holder_after

        gross = recs[0].gross_acres
        gross_frac = try_parse_acres(gross) if str(gross).strip() else None
        nma = ""
        interest_txt = ""
        interest_decimal = None
        if current_interest is not None:
            interest_txt = format_fraction(current_interest)
            interest_decimal = round(float(current_interest), 6)
            if gross_frac is not None:
                nma = format_acres(net_acres(current_interest, gross_frac))

        ledger.append(
            {
                "tract_key": key,
                "tract_legal": tract_legal,
                "gross_acres": gross,
                "instruments": len(recs),
                "ties_out": not result.needs_examiner_review,
                "current_owner": current_owner or "Undetermined",
                "current_interest": interest_txt,
                "current_interest_decimal": interest_decimal,
                "net_mineral_acres": nma,
                "review_reasons": list(result.review_reasons),
            }
        )
    return ledger


def build_title_analysis(
    conveyances: Sequence[ConveyanceFact],
    section: str = "Unspecified",
) -> Dict[str, Any]:
    """Reconcile a set of conveyance facts into a full title analysis payload.

    Non-ownership documents (leases, affidavits, plats, ...) are carried as
    supporting evidence and are not fed into the interest chain.
    """
    chain_docs = [f for f in conveyances if f.is_conveyance]
    supporting = [f for f in conveyances if not f.is_conveyance]

    ogl_records = [
        OGLRecord(
            instrument_number=f.instrument_number,
            grantor=f.grantor,
            grantee=f.grantee,
            conveyed_interest=f.conveyed_interest,
            legal_description=f.legal_description,
            doc_type=f.doc_type,
            instrument_date=f.instrument_date,
            gross_acres=f.gross_acres,
        )
        for f in chain_docs
    ]
    # Every conveyance is its own runsheet note (keyed by instrument number), so
    # the OGL<->runsheet cross-reference is satisfied for well-formed input and a
    # genuinely missing/duplicate instrument still surfaces as a chain break.
    runsheet_notes = [
        RunsheetNote(
            instrument_number=f.instrument_number,
            note=f.doc_type,
            legal_description=f.legal_description,
        )
        for f in chain_docs
        if f.instrument_number
    ]

    build = chain_to_report(ogl_records, runsheet_notes, section=section)
    validation = validate_report(build.report, Requirements())
    ledger = _ownership_ledger(chain_docs)

    rows = [r.model_dump() for r in build.report.rows]
    rows_review = sum(1 for r in build.report.rows if r.needs_review)
    over_conveyances = sum(
        1 for r in build.report.rows if "over-conveyance" in (r.remarks or "").lower()
    )
    # horizon's gate passes with "review" issues by design; a landman still needs
    # a single headline verdict, so REVIEW dominates when anything needs a human.
    clean = (
        validation.passed
        and rows_review == 0
        and over_conveyances == 0
        and not build.chain_breaks
    )
    overall_status = "CLEAR" if clean else "REVIEW REQUIRED"

    analysis: Dict[str, Any] = {
        "section": section,
        "generated_at": _utc_now(),
        "recipe_version": RECIPE_VERSION,
        "summary": {
            "documents": len(conveyances),
            "conveyance_documents": len(chain_docs),
            "supporting_documents": len(supporting),
            "tracts": len(ledger),
            "chain_rows": len(rows),
            "rows_need_review": rows_review,
            "over_conveyances": over_conveyances,
            "chain_breaks": len(build.chain_breaks),
            "validation_passed": validation.passed,
            "overall_status": overall_status,
        },
        "ownership": ledger,
        "chain_rows": rows,
        "documents": [f.to_dict() for f in conveyances],
        "chain_breaks": [
            {"instrument_key": c.key, "status": c.status} for c in build.chain_breaks
        ],
        "validation": {
            "passed": validation.passed,
            "summary": validation.summary(),
            "issues": [i.model_dump() for i in validation.issues],
        },
    }
    analysis["report_markdown"] = _render_report_markdown(analysis)
    return analysis


def _render_report_markdown(analysis: Dict[str, Any]) -> str:
    s = analysis["summary"]
    lines: List[str] = []
    lines.append(f"# Cursory Title Report -- {analysis['section']}")
    lines.append("")
    lines.append(f"_Generated {analysis['generated_at']} by DataBossX Landman Helper "
                 f"({analysis['recipe_version']})._")
    lines.append("")
    lines.append("> Draft work product. Unreviewed output is not a certified abstract, "
                 "title opinion, or a substitute for a licensed title examiner or attorney.")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Documents examined: **{s['documents']}** "
                 f"({s['conveyance_documents']} conveyances, {s['supporting_documents']} supporting)")
    lines.append(f"- Tracts: **{s['tracts']}**")
    lines.append(f"- Chain rows: **{s['chain_rows']}** "
                 f"({s['rows_need_review']} need examiner review)")
    lines.append(f"- Over-conveyances detected: **{s['over_conveyances']}**")
    lines.append(f"- Overall status: **{s['overall_status']}**")
    lines.append("")
    lines.append("## Current mineral ownership")
    if analysis["ownership"]:
        lines.append("| Tract | Current owner | Interest | Net mineral acres | Ties out |")
        lines.append("| --- | --- | --- | --- | --- |")
        for o in analysis["ownership"]:
            lines.append(
                f"| {o['tract_legal']} | {o['current_owner']} | "
                f"{o['current_interest'] or '--'} | {o['net_mineral_acres'] or '--'} | "
                f"{'yes' if o['ties_out'] else 'REVIEW'} |"
            )
    else:
        lines.append("_No ownership-conveying instruments found._")
    lines.append("")
    lines.append("## Chain of title")
    if analysis["chain_rows"]:
        lines.append("| Instrument | Grantor | Grantee | Conveyed | Retained | Net acres | Status |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for r in analysis["chain_rows"]:
            lines.append(
                f"| {r.get('instrument_number') or '--'} | {r.get('grantor') or '--'} | "
                f"{r.get('grantee') or '--'} | {r.get('conveyed_interest') or '--'} | "
                f"{r.get('retained_interest') or '--'} | {r.get('net_mineral_acres') or '--'} | "
                f"{r.get('status')} |"
            )
    else:
        lines.append("_No chain rows._")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Foundation integration: documents in the vault -> persisted derived artifact
# ---------------------------------------------------------------------------
_TEXT_SUFFIXES = {".txt", ".md", ".csv", ".text", ".log"}


def _extract_text(path: Path, logical_key: str) -> Tuple[str, bool]:
    """Best-effort text extraction from a file; returns ``(text, ocr_used)``.

    Plain-text formats are read directly; binary formats (pdf/docx/image/xlsx)
    reuse the grocery pipeline's extractors when their optional backends are
    installed (pdfplumber/PyMuPDF for PDFs, python-docx for Word, pytesseract +
    the tesseract binary for images/scanned PDFs). When a backend is missing the
    document is still recorded and its fields are flagged for review -- never
    fabricated.
    """
    suffix = Path(logical_key).suffix.lower()
    try:
        if suffix in _TEXT_SUFFIXES or suffix == "":
            return path.read_text(encoding="utf-8", errors="replace"), False
        if suffix in _grp.PDF_EXT:
            text, _method, ocr, _note = _grp._extract_pdf(path)
            return text, ocr
        if suffix in _grp.WORD_EXT:
            text, _method, ocr, _note = _grp._extract_docx(path)
            return text, ocr
        if suffix in _grp.IMAGE_EXT:
            text, _method, ocr, _note = _grp._extract_image(path)
            return text, ocr
        if suffix in _grp.EXCEL_EXT:
            text, _method, ocr, _note = _grp._extract_xlsx(path)
            return text, ocr
        return path.read_text(encoding="utf-8", errors="replace"), False
    except Exception:
        return "", False


def load_text_from_bytes(filename: str, data: bytes) -> Tuple[str, bool]:
    """Extract text from raw uploaded bytes (used for the upload preview)."""
    import tempfile

    suffix = Path(filename).suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(data)
        tmp.flush()
        return _extract_text(Path(tmp.name), filename)


def _sanitize_filename(name: str) -> str:
    name = Path(name or "document").name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "document"
    return name[:120]


def register_document(
    config: DataBossConfig,
    project_id: str,
    filename: str,
    data: bytes,
) -> Dict[str, Any]:
    """Store an uploaded title document as a content-addressed project asset.

    Idempotent: re-uploading identical bytes under the same logical key does not
    create duplicate rows. Reuses the foundation vault + audit log.
    """
    db = DataBossDatabase(config.project_db_path(project_id))
    inbox = config.project_root(project_id) / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    safe = _sanitize_filename(filename)
    disk_path = inbox / safe
    disk_path.write_bytes(data)

    stored = copy_file_to_vault(disk_path, config.project_vault_root(project_id))
    with db.connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO assets (project_id, logical_key, asset_class, first_seen_at)
            VALUES (?, ?, 'source_document', CURRENT_TIMESTAMP)
            """,
            (project_id, safe),
        )
        asset_row = conn.execute(
            "SELECT id FROM assets WHERE project_id = ? AND logical_key = ? AND asset_class = 'source_document'",
            (project_id, safe),
        ).fetchone()
        asset_id = int(asset_row["id"])
        conn.execute(
            """
            INSERT OR IGNORE INTO asset_versions (
                asset_id, source_snapshot_id, sha256, mime_type, byte_size, original_locator,
                vault_path, provider_version, duplicate_of_asset_version_id, created_at
            ) VALUES (?, NULL, ?, ?, ?, ?, ?, '', NULL, CURRENT_TIMESTAMP)
            """,
            (
                asset_id,
                stored.sha256,
                "text/plain",
                stored.byte_size,
                str(disk_path),
                str(stored.vault_path),
            ),
        )
        conn.commit()
    db.audit(
        project_id,
        "document.registered",
        "asset",
        safe,
        json.dumps({"sha256": stored.sha256, "byte_size": stored.byte_size}, sort_keys=True),
    )
    return {"filename": safe, "sha256": stored.sha256, "byte_size": stored.byte_size}


def _project_documents(config: DataBossConfig, project_id: str) -> List[Tuple[str, str, int]]:
    """Return (logical_key, vault_path, asset_version_id) for source documents."""
    db = DataBossDatabase(config.project_db_path(project_id))
    rows = db.fetchall(
        """
        SELECT a.logical_key AS logical_key, av.vault_path AS vault_path, av.id AS av_id
          FROM assets a
          JOIN asset_versions av ON av.asset_id = a.id
         WHERE a.project_id = ? AND a.asset_class = 'source_document'
         ORDER BY a.id, av.id
        """,
        (project_id,),
    )
    return [(r["logical_key"], r["vault_path"], int(r["av_id"])) for r in rows]


def analyze_project(
    config: DataBossConfig,
    project_id: str,
    section: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the full landman analysis over a project's registered documents.

    Extracts a conveyance fact per source document, reconciles the chain with
    exact interest math, validates it, then persists the analysis as a
    ``derived_artifact`` (with lineage to the source asset versions) and a JSON
    file in the project's artifacts directory, and writes an audit event.
    """
    docs = _project_documents(config, project_id)
    conveyances: List[ConveyanceFact] = []
    lineage_av_ids: List[int] = []
    for logical_key, vault_path, av_id in docs:
        text, ocr_used = _extract_text(Path(vault_path), logical_key)
        fact = extract_conveyance(logical_key, text)
        fact.ocr_used = ocr_used
        conveyances.append(fact)
        lineage_av_ids.append(av_id)

    if section is None:
        section = _infer_section(conveyances)

    analysis = build_title_analysis(conveyances, section=section)

    # Persist as a derived artifact + lineage + JSON file + audit event.
    db = DataBossDatabase(config.project_db_path(project_id))
    artifact_id = db.execute(
        """
        INSERT INTO derived_artifacts (project_id, artifact_type, recipe_version)
        VALUES (?, 'title_analysis', ?)
        """,
        (project_id, RECIPE_VERSION),
    )
    with db.connect() as conn:
        for av_id in lineage_av_ids:
            conn.execute(
                "INSERT INTO artifact_lineage (derived_artifact_id, asset_version_id) VALUES (?, ?)",
                (artifact_id, av_id),
            )
        conn.commit()

    run_id = _record_analysis_run(db, project_id, section, artifact_id)

    artifacts_dir = config.project_artifacts_root(project_id)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    out_path = artifacts_dir / f"title_analysis_{artifact_id}.json"
    analysis["artifact_id"] = artifact_id
    analysis["artifact_path"] = str(out_path)
    analysis["run_id"] = run_id
    out_path.write_text(json.dumps(analysis, indent=2, sort_keys=True), encoding="utf-8")

    db.audit(
        project_id,
        "title.analyzed",
        "derived_artifact",
        str(artifact_id),
        json.dumps({"section": section, "run_id": run_id, **analysis["summary"]}, sort_keys=True),
    )
    return analysis


def _record_analysis_run(
    db: DataBossDatabase, project_id: str, section: str, artifact_id: int
) -> int:
    """Record the analysis as a completed run/task/attempt in the workflow spine.

    Turns each analysis into a first-class, tracked run (mirroring the foundation
    intake-run pattern) and ties the produced artifact to the task attempt via
    ``log_artifact_id`` -- so the runs/tasks tables reflect real work, not just
    the seeded intake plan.
    """
    workflow_name = "title_analysis"
    workflow_id = db.execute(
        "INSERT OR IGNORE INTO workflow_definitions (name, version) VALUES (?, ?)",
        (workflow_name, "1.0.0"),
    )
    if not workflow_id:
        row = db.fetchone(
            "SELECT id FROM workflow_definitions WHERE name = ? ORDER BY id DESC LIMIT 1",
            (workflow_name,),
        )
        workflow_id = int(row["id"])
    run_id = db.execute(
        "INSERT INTO runs (project_id, workflow_id, status, completed_at) "
        "VALUES (?, ?, 'COMPLETED', CURRENT_TIMESTAMP)",
        (project_id, workflow_id),
    )
    task_id = db.execute(
        "INSERT INTO tasks (run_id, task_type, state, priority, payload_json) "
        "VALUES (?, 'ANALYZE_TITLE', 'SUCCEEDED', 100, ?)",
        (run_id, json.dumps({"section": section}, sort_keys=True)),
    )
    db.execute(
        "INSERT INTO task_attempts (task_id, worker_name, completed_at, status, log_artifact_id) "
        "VALUES (?, 'landman', CURRENT_TIMESTAMP, 'SUCCEEDED', ?)",
        (task_id, artifact_id),
    )
    return run_id


def project_activity(
    config: DataBossConfig, project_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """Return the project's append-only audit trail (newest first).

    Every step -- project creation, source/document registration, analysis, and
    export -- writes an ``audit_events`` row; this surfaces that chain of custody
    for the command-center UI.
    """
    db_path = config.project_db_path(project_id)
    if not db_path.exists():
        return []
    db = DataBossDatabase(db_path)
    rows = db.fetchall(
        """
        SELECT event_type, entity_type, entity_id, payload_json, created_at
          FROM audit_events
         WHERE project_id = ?
         ORDER BY id DESC LIMIT ?
        """,
        (project_id, limit),
    )
    events: List[Dict[str, Any]] = []
    for r in rows:
        try:
            payload = json.loads(r["payload_json"]) if r["payload_json"] else {}
        except (json.JSONDecodeError, TypeError):
            payload = {}
        events.append(
            {
                "event_type": r["event_type"],
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "created_at": r["created_at"],
                "payload": payload,
            }
        )
    return events


def latest_analysis(config: DataBossConfig, project_id: str) -> Optional[Dict[str, Any]]:
    """Load the most recent persisted title analysis for a project, or None."""
    db_path = config.project_db_path(project_id)
    if not db_path.exists():
        return None
    db = DataBossDatabase(db_path)
    art = db.fetchone(
        """
        SELECT id FROM derived_artifacts
         WHERE project_id = ? AND artifact_type = 'title_analysis'
         ORDER BY id DESC LIMIT 1
        """,
        (project_id,),
    )
    if art is None:
        return None
    path = config.project_artifacts_root(project_id) / f"title_analysis_{art['id']}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def export_report(config: DataBossConfig, project_id: str) -> Dict[str, Any]:
    """Render the reconciled analysis into a landman's real deliverables.

    Writes the canonical cursory title report as ``.xlsx`` (via horizon's
    ``report_io``) and the examiner worklist as ``.csv`` (via horizon's
    ``artifacts``) into the project's exports/review directories, and records
    each as an auditable ``derived_artifact``. Raises ``ValueError`` when the
    project has not been analyzed yet.
    """
    analysis = latest_analysis(config, project_id)
    if analysis is None:
        raise ValueError("No analysis to export; run analyze first.")

    rows = [TitleRow(**r) for r in analysis.get("chain_rows", [])]
    report = ReportModel(
        section=analysis.get("section", "Unspecified"), source="landman", rows=rows
    )

    exports_dir = config.project_exports_root(project_id)
    review_dir = config.project_review_root(project_id)
    exports_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = exports_dir / "cursory_title_report.xlsx"
    worklist_path = review_dir / "examiner_worklist.csv"

    write_report(report, xlsx_path)
    worklist_rows = write_review_worklist(report, worklist_path)

    db = DataBossDatabase(config.project_db_path(project_id))
    artifact_id = db.execute(
        """
        INSERT INTO derived_artifacts (project_id, artifact_type, recipe_version)
        VALUES (?, 'title_report_export', ?)
        """,
        (project_id, RECIPE_VERSION),
    )
    db.audit(
        project_id,
        "report.exported",
        "derived_artifact",
        str(artifact_id),
        json.dumps(
            {"xlsx": str(xlsx_path), "worklist_rows": worklist_rows}, sort_keys=True
        ),
    )
    return {
        "xlsx_path": str(xlsx_path),
        "worklist_path": str(worklist_path),
        "worklist_rows": worklist_rows,
    }


def _infer_section(conveyances: Sequence[ConveyanceFact]) -> str:
    """Pick the most common legal description as the report section label."""
    counts: Dict[str, int] = {}
    for f in conveyances:
        if f.legal_description:
            counts[f.legal_description] = counts.get(f.legal_description, 0) + 1
    if not counts:
        return "Unspecified"
    return max(counts.items(), key=lambda kv: kv[1])[0]


# ---------------------------------------------------------------------------
# One-click demo: a synthetic Roger-Mills-style corpus that exercises the
# happy path (a clean tie-out) and the guardrails (an over-conveyance).
# ---------------------------------------------------------------------------
SAMPLE_DEEDS: List[Tuple[str, str]] = [
    (
        "01_mineral_deed_anderson_baker.txt",
        """MINERAL DEED

Grantor: Alice Anderson
Grantee: Bob Baker

For and in consideration of Ten Dollars and other good and valuable
consideration, Grantor does hereby grant, bargain, sell and convey unto Grantee
an undivided 1/2 interest in and to all of the oil, gas and other minerals in
and under and that may be produced from the following described land situated in
Roger Mills County, Oklahoma, to-wit:

Section 31, T12N, R24W, containing 640 gross acres, more or less.

Instrument No. 20180001. Instrument Date: 2018-03-05.
""",
    ),
    (
        "02_mineral_deed_baker_chen.txt",
        """MINERAL DEED

Grantor: Bob Baker
Grantee: Carol Chen

Grantor does hereby convey unto Grantee an undivided 1/2 interest in and to all
of the oil, gas and other minerals in and under the following described land in
Roger Mills County, Oklahoma:

Section 31, T12N, R24W, containing 640 gross acres.

Instrument No. 20190002. Instrument Date: 2019-06-14.
""",
    ),
    (
        "03_warranty_deed_chen_diaz.txt",
        """WARRANTY DEED

Grantor: Carol Chen
Grantee: David Diaz

Grantor conveys and warrants unto Grantee an undivided 1/4 interest in and to
all of the oil, gas and other minerals in, on and under the following described
real property in Roger Mills County, Oklahoma:

Section 31, T12N, R24W, containing 640 gross acres.

Instrument No. 20200003. Instrument Date: 2020-01-22.
""",
    ),
    (
        "04_mineral_deed_diaz_evans.txt",
        """MINERAL DEED

Grantor: David Diaz
Grantee: Erin Evans

Grantor grants and conveys unto Grantee an undivided 1/8 interest in and to all
of the oil, gas and other minerals under the following described land in Roger
Mills County, Oklahoma:

Section 31, T12N, R24W, containing 640 gross acres.

Instrument No. 20210004. Instrument Date: 2021-09-30.
""",
    ),
    (
        "05_oil_and_gas_lease_evans_operator.txt",
        """OIL AND GAS LEASE

Lessor: Erin Evans
Lessee: Meridian Operating LLC

This paid-up Oil and Gas Lease covers the following land in Roger Mills County,
Oklahoma: Section 31, T12N, R24W, containing 640 gross acres, reserving unto
Lessor a royalty of 3/16.

Instrument No. 20220010. Instrument Date: 2022-02-01.
""",
    ),
    (
        "06_mineral_deed_frank_isaac.txt",
        """MINERAL DEED

Grantor: Frank Fisher
Grantee: Isaac Ingram

Grantor conveys unto Grantee an undivided 1/2 interest in and to all of the oil,
gas and other minerals under the following described land in Roger Mills County,
Oklahoma:

Section 32, T12N, R24W, containing 320 gross acres.

Instrument No. 20200055. Instrument Date: 2020-05-10.
""",
    ),
    (
        "07_mineral_deed_isaac_jack_overconveyance.txt",
        """MINERAL DEED

Grantor: Isaac Ingram
Grantee: Jack Jones

Grantor does hereby convey unto Grantee an undivided 3/4 interest in and to all
of the oil, gas and other minerals under the following described land in Roger
Mills County, Oklahoma:

Section 32, T12N, R24W, containing 320 gross acres.

Instrument No. 20210066. Instrument Date: 2021-07-19.
""",
    ),
]


def seed_demo_project(
    config: DataBossConfig,
    *,
    name: str = "Roger Mills 31-12N-24W (Demo)",
    jurisdiction_code: str = "OK",
) -> Dict[str, Any]:
    """Create a fully-seeded demo project and run the analysis end to end.

    Returns ``{"project_id", "analysis"}``. The corpus exercises a clean
    four-deed tie-out on Section 31 (current owner determined, net acres
    computed) plus an over-conveyance on Section 32 that the engine refuses to
    balance -- demonstrating both the math and the guardrails.
    """
    # Local import avoids importing horizon/grocery when only the foundation
    # intake is used elsewhere.
    from .intake import create_project

    project = create_project(config, name=name, jurisdiction_code=jurisdiction_code)
    for filename, text in SAMPLE_DEEDS:
        register_document(config, project.project_id, filename, text.encode("utf-8"))
    analysis = analyze_project(config, project.project_id, section="Section 31, T12N, R24W")
    return {"project_id": project.project_id, "analysis": analysis}
