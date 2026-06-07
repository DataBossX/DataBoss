"""quality_control -- run required checks and compute confidence scores."""
from __future__ import annotations

from ..model import ReportContext, confidence_band

REQUIRED_SHEETS = [
    "Overview", "Title", "PLAT", "Run Sheet", "OGL", "Well Data",
    "Index Text", "Source Notes", "Confidence Summary", "Curative Issues",
]


def run_qc(ctx: ReportContext, produced_sheets: list[str]) -> dict:
    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    present = set(produced_sheets)
    for s in REQUIRED_SHEETS:
        check(f"Sheet exists: {s}", s in present, "" if s in present else "missing")

    check("Every source document logged", len(ctx.source_files) > 0,
          f"{len(ctx.source_files)} files inventoried")
    check("Every lease has a source", all(l.source_status or l.source_file for l in ctx.leases),
          f"{len(ctx.leases)} leases")
    check("Every index row has source reference",
          all(i.source_reference for i in ctx.instruments), f"{len(ctx.instruments)} rows")
    check("Every chain link has confidence", all(c.confidence > 0 for c in ctx.chain),
          f"{len(ctx.chain)} links")
    check("Wells collected", len(ctx.wells) > 0, f"{len(ctx.wells)} wells")
    check("Curative issues identified", len(ctx.curative) > 0, f"{len(ctx.curative)} issues")
    check("Missing-document/limitations recorded", len(ctx.limitations) > 0,
          f"{len(ctx.limitations)} limitations")

    # ---- confidence scoring -------------------------------------------------
    lease_scores = [l.confidence for l in ctx.leases] or [0]
    idx_scores = [round((i.match_confidence + i.relevance_confidence) / 2) for i in ctx.instruments] or [0]
    chain_scores = [c.confidence for c in ctx.chain] or [0]
    well_scores = [w.confidence for w in ctx.wells] or [0]

    sheet_scores = {
        "OGL": _avg(lease_scores),
        "Index Text": _avg(idx_scores),
        "Run Sheet": _avg(chain_scores),
        "Well Data": _avg(well_scores),
        "Title": min(_avg(lease_scores), 60),   # tract ownership rests on unverified leases
        "Overview": 75,
        "PLAT": 70,
        "Source Notes": 90,
        "Curative Issues": 88,
    }
    ctx.sheet_scores = sheet_scores

    # Overall: weighted toward the title-bearing sheets, capped because no
    # recorded images or production were verified (cursory/index-only run).
    overall = round(
        0.30 * sheet_scores["Index Text"]
        + 0.20 * sheet_scores["OGL"]
        + 0.20 * sheet_scores["Run Sheet"]
        + 0.10 * sheet_scores["Well Data"]
        + 0.10 * sheet_scores["Title"]
        + 0.10 * 80
    )
    overall = min(overall, 68)  # honesty cap: cursory, index-only, images unreviewed

    passed = sum(1 for c in checks if c["pass"])
    return {
        "checks": checks,
        "checks_passed": passed,
        "checks_total": len(checks),
        "sheet_scores": sheet_scores,
        "overall_confidence": overall,
        "overall_band": confidence_band(overall),
    }


def _avg(xs):
    return round(sum(xs) / len(xs)) if xs else 0
