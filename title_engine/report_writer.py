"""
Report Writer — generates a client-ready narrative title opinion report.

Outputs a structured plain-text / markdown report covering:
- Executive summary
- Chain of title narrative (lease, assignment, mineral)
- Identified gaps and curative requirements
- Source documentation inventory
- Disclaimer
"""

import datetime
from pathlib import Path
from typing import List, Dict, Any

from .chain_builder import ChainBuilder, ChainRow, EXPORT_COLUMNS

# ── Constants ─────────────────────────────────────────────────────────────────

SECTION   = "27"
TOWNSHIP  = "11N"
RANGE     = "25W"
COUNTY    = "Beckham"
STATE     = "Oklahoma"
LEGAL_KEY = f"{SECTION}-{TOWNSHIP}-{RANGE}W"

DISCLAIMER = """
DISCLAIMER
----------
This report is prepared solely as a research aid and does not constitute a
legal title opinion. All information herein is derived from county records
searches and automated document extraction. No fabricated or inferred values
have been introduced — fields that lack documentary support are labeled
UNKNOWN. This report should be reviewed and certified by a licensed Oklahoma
attorney before reliance in any transaction.
""".strip()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.date.today().strftime("%B %d, %Y")


def _section_header(title: str, char: str = "=") -> str:
    line = char * len(title)
    return f"\n{title}\n{line}"


def _bullet(items: List[str], indent: int = 2) -> str:
    prefix = " " * indent + "• "
    return "\n".join(prefix + i for i in items) if items else f"{'  ' * indent}(none)"


def _row_summary(row: ChainRow) -> str:
    date_part = row.recording_date if row.recording_date != "UNKNOWN" else row.doc_date
    book_page  = f"Book {row.book} / Page {row.page}" if row.book != "UNKNOWN" else ""
    inst_no    = f"Inst #{row.instrument_number}" if row.instrument_number != "UNKNOWN" else ""
    ref        = " | ".join(x for x in [inst_no, book_page] if x) or "No reference"
    parties    = []
    if row.lessor   != "UNKNOWN": parties.append(f"Lessor: {row.lessor}")
    if row.lessee   != "UNKNOWN": parties.append(f"Lessee: {row.lessee}")
    if row.grantor  != "UNKNOWN": parties.append(f"Grantor: {row.grantor}")
    if row.grantee  != "UNKNOWN": parties.append(f"Grantee: {row.grantee}")
    if row.assignor != "UNKNOWN": parties.append(f"Assignor: {row.assignor}")
    if row.assignee != "UNKNOWN": parties.append(f"Assignee: {row.assignee}")
    party_str = " | ".join(parties[:2]) if parties else "Parties unknown"
    return f"  [{date_part}] {row.instrument_type} — {ref}\n    {party_str} | Confidence: {row.confidence}"


# ── Sections ──────────────────────────────────────────────────────────────────

def _write_header(stats: Dict[str, Any]) -> str:
    lines = [
        "=" * 72,
        f"  TITLE RESEARCH REPORT",
        f"  Section {SECTION}, Township {TOWNSHIP}, Range {RANGE}",
        f"  {COUNTY} County, {STATE}",
        f"  Prepared: {_today()}",
        "=" * 72,
        "",
        f"  Total instruments found:   {stats.get('total', 0)}",
        f"  Section 27 confirmed:      {stats.get('section_27', 0)}",
        f"  Images downloaded:         {stats.get('dl_done', 0)}",
        f"  Documents OCR'd:           {stats.get('ocr_done', 0)}",
        f"  Documents extracted:       {stats.get('ext_done', 0)}",
        f"  Needing review:            {stats.get('needs_review', 0)}",
        f"  OKCR API cost:             ${stats.get('okcr_cost', 0):.4f}",
        f"  AI extraction cost:        ${stats.get('ai_cost', 0):.4f}",
        f"  Total cost:                ${stats.get('total_cost', 0):.4f}",
        "",
    ]
    return "\n".join(lines)


def _write_executive_summary(builder: ChainBuilder) -> str:
    n_leases  = len(builder.lease_rows)
    n_asgn    = len(builder.asgn_rows)
    n_mineral = len(builder.mineral_rows)
    n_gaps    = len(builder.gaps)
    n_missing = len(builder.missing)
    n_div     = len(builder.diversified_rows)

    status = "CLEAR" if n_gaps == 0 and n_missing == 0 else "CURATIVE REQUIRED"

    lines = [
        _section_header("EXECUTIVE SUMMARY"),
        "",
        f"  Chain status:  {status}",
        f"  Oil & Gas Leases / Memoranda:  {n_leases}",
        f"  Assignments / Releases:        {n_asgn}",
        f"  Mineral / Deed instruments:    {n_mineral}",
        f"  Chain gaps identified:         {n_gaps}",
        f"  Referenced but missing docs:   {n_missing}",
        f"  Diversified Energy instruments:{n_div}",
    ]

    if n_gaps or n_missing:
        lines += [
            "",
            "  *** TITLE CANNOT BE CERTIFIED WITHOUT CURATIVE ACTION ***",
            "  See 'Curative Requirements' section for details.",
        ]
    else:
        lines += [
            "",
            "  No chain gaps or missing instruments detected based on available records.",
            "  Standard title curative review is still recommended before closing.",
        ]

    return "\n".join(lines)


def _write_lease_chain(rows: List[ChainRow]) -> str:
    if not rows:
        return _section_header("OIL & GAS LEASE CHAIN") + "\n\n  (No lease instruments found)\n"

    lines = [_section_header("OIL & GAS LEASE CHAIN"), ""]
    for i, row in enumerate(rows, 1):
        lines.append(f"  {i:>3}. {_row_summary(row)}")
        if row.royalty      != "UNKNOWN": lines.append(f"       Royalty: {row.royalty}")
        if row.primary_term != "UNKNOWN": lines.append(f"       Primary Term: {row.primary_term}")
        if row.depth_clause != "UNKNOWN": lines.append(f"       Depth Clause: {row.depth_clause}")
        if row.pugh_clause  != "UNKNOWN": lines.append(f"       Pugh Clause: {row.pugh_clause}")
        if row.gross_acres  != "UNKNOWN": lines.append(f"       Gross Acres: {row.gross_acres}")
        lines.append(f"       Status: {row.chain_status}  |  Source: {row.source_link}")
        lines.append("")
    return "\n".join(lines)


def _write_assignment_chain(rows: List[ChainRow]) -> str:
    if not rows:
        return _section_header("ASSIGNMENT CHAIN") + "\n\n  (No assignment instruments found)\n"

    lines = [_section_header("ASSIGNMENT CHAIN"), ""]
    for i, row in enumerate(rows, 1):
        lines.append(f"  {i:>3}. {_row_summary(row)}")
        if row.net_leasehold_acres != "UNKNOWN":
            lines.append(f"       Net Leasehold Acres: {row.net_leasehold_acres}")
        if row.working_interest != "UNKNOWN":
            lines.append(f"       Working Interest: {row.working_interest}")
        if row.nri != "UNKNOWN":
            lines.append(f"       NRI: {row.nri}")
        if row.problem_gap:
            lines.append(f"       *** GAP: {row.problem_gap}")
        lines.append(f"       Status: {row.chain_status}  |  Source: {row.source_link}")
        lines.append("")
    return "\n".join(lines)


def _write_mineral_chain(rows: List[ChainRow]) -> str:
    if not rows:
        return _section_header("MINERAL OWNERSHIP CHAIN") + "\n\n  (No mineral deed instruments found)\n"

    lines = [_section_header("MINERAL OWNERSHIP CHAIN"), ""]
    for i, row in enumerate(rows, 1):
        lines.append(f"  {i:>3}. {_row_summary(row)}")
        if row.net_mineral_acres != "UNKNOWN":
            lines.append(f"       Net Mineral Acres: {row.net_mineral_acres}")
        if row.quarter_call != "UNKNOWN":
            lines.append(f"       Quarter Call: {row.quarter_call}")
        lines.append(f"       Status: {row.chain_status}  |  Source: {row.source_link}")
        lines.append("")
    return "\n".join(lines)


def _write_diversified(rows: List[ChainRow]) -> str:
    lines = [_section_header("DIVERSIFIED ENERGY — INSTRUMENT INVENTORY"), ""]
    if not rows:
        lines.append("  (No instruments identified as Diversified Energy / affiliated entities)\n")
        return "\n".join(lines)

    for row in rows:
        lines.append(f"  Entity: {row.diversified_entity}")
        lines.append(f"  {_row_summary(row)}")
        lines.append("")
    return "\n".join(lines)


def _write_curative(gaps: List[Dict], missing: List[Dict]) -> str:
    lines = [_section_header("CURATIVE REQUIREMENTS"), ""]

    if not gaps and not missing:
        lines.append("  No curative action required based on available records.")
        lines.append("  Standard legal review still recommended.\n")
        return "\n".join(lines)

    if gaps:
        lines.append("  Chain Gaps (require vesting instrument or affidavit):")
        for g in gaps:
            lines.append(f"    • Instrument {g['instrument_number']} — {g['problem']}")
            lines.append(f"      Action: {g['curative']}")
        lines.append("")

    if missing:
        lines.append("  Referenced but Missing Instruments:")
        for m in missing:
            lines.append(f"    • {m.get('missing_instrument', 'Unknown')} — {m.get('type', '')}")
            lines.append(f"      Referenced in: {m.get('referenced_in', '')}")
            lines.append(f"      Action: {m.get('curative', '')}")
        lines.append("")

    return "\n".join(lines)


def _write_source_inventory(all_rows: List[ChainRow]) -> str:
    lines = [_section_header("SOURCE DOCUMENTATION INVENTORY"), ""]
    has_image  = [r for r in all_rows if "pdf" in r.source_link.lower() or r.source_link.startswith("/")]
    index_only = [r for r in all_rows if r.source_link.startswith("http")]
    no_link    = [r for r in all_rows if r.source_link.startswith("NO LINK")]

    lines.append(f"  Image reviewed (PDF downloaded):  {len(has_image)}")
    lines.append(f"  Index only (no image):            {len(index_only)}")
    lines.append(f"  No source link:                   {len(no_link)}")
    lines.append("")

    if no_link:
        lines.append("  Instruments with NO SOURCE LINK — require manual location:")
        for r in no_link:
            lines.append(f"    • {r.instrument_type} | {r.instrument_number} | "
                         f"Book {r.book} / Page {r.page} | {r.doc_date}")

    return "\n".join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

def write_report(builder: ChainBuilder,
                 stats: Dict[str, Any],
                 output_path: Path) -> Path:
    """
    Generate the narrative report and write to output_path.
    Returns the path written.
    """
    sections = [
        _write_header(stats),
        _write_executive_summary(builder),
        _write_lease_chain(builder.lease_rows),
        _write_assignment_chain(builder.asgn_rows),
        _write_mineral_chain(builder.mineral_rows),
        _write_diversified(builder.diversified_rows),
        _write_curative(builder.gaps, builder.missing),
        _write_source_inventory(builder.all_rows),
        "\n" + DISCLAIMER + "\n",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(sections), encoding="utf-8")
    return output_path
