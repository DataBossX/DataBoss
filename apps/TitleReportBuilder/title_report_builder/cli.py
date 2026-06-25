"""Command-line interface (stdlib argparse — zero extra runtime deps).

Examples:
  python -m title_report_builder discover  --project "/path/to/Roger Mills"
  python -m title_report_builder ocr       --pdf index.pdf --out ./_work --dpi 300
  python -m title_report_builder foot       --workbook report.xlsx --out fixed.xlsx \
        --tracts "Tract 1,Tract 2,Tract 3,Tract 4,Tract 5,Tract 6,Tract 7,Tract 8"
  python -m title_report_builder qa        --workbook report.xlsx
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from .utils import get_logger, ensure_dirs

log = get_logger()


def _discover(a):
    from .discovery import discover, write_manifest
    files = discover(a.project, recurse=not a.no_recurse)
    if a.manifest:
        ensure_dirs(Path(a.manifest).parent)
        write_manifest(files, a.manifest)
    log.info("discovered %d files under %s", len(files), a.project)
    print(json.dumps({"count": len(files), "manifest": a.manifest}, indent=2))


def _ocr(a):
    from .extractors.pdf_extractor import ocr_pdf, render_pages
    ensure_dirs(a.out)
    if a.render:
        paths = render_pages(a.pdf, a.out, dpi=a.dpi)
        log.info("rendered %d pages", len(paths))
    pages = ocr_pdf(a.pdf, dpi=a.dpi)
    out = Path(a.out) / "ocr_text"
    ensure_dirs(out)
    for i, t in enumerate(pages, 1):
        (out / f"page_{i:03d}.txt").write_text(t)
    print(json.dumps({"pages": len(pages), "text_dir": str(out)}, indent=2))


def _foot(a):
    from .report.workbook_builder import repair_all_tracts
    tracts = [t.strip() for t in a.tracts.split(",") if t.strip()]
    res = repair_all_tracts(a.workbook, tracts, a.out)
    foots = {k: v["foots"] for k, v in res["tracts"].items()}
    verified = all(v["verified"] for v in res["tracts"].values())
    log.info("footing repaired; fractions replaced=%d; verified=%s",
             res["fractions_replaced"], verified)
    print(json.dumps({
        "foots": foots,
        "verified": verified,
        "note": ("foots=null means the formula was written correctly but could not be "
                 "numerically verified here (no cached values; open/recalc in Excel)")
        if not verified else "all tracts numerically verified to foot to D5",
        "fractions": res["fractions_replaced"], "out": a.out}, indent=2))


def _qa(a):
    from .report.qa import scan
    rep = scan(a.workbook)
    print(json.dumps({
        "passed": rep.passed, "cached_errors": rep.cached_errors,
        "formula_error_literals": rep.formula_error_literals,
        "broken_link_targets": rep.broken_link_targets[:10],
        "error_samples": rep.error_samples,
    }, indent=2))
    sys.exit(0 if rep.passed else 1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="title_report_builder",
                                description="Cursory title report builder pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="recursive source manifest")
    d.add_argument("--project", required=True)
    d.add_argument("--manifest", default="")
    d.add_argument("--no-recurse", action="store_true")
    d.set_defaults(func=_discover)

    o = sub.add_parser("ocr", help="render + OCR a PDF index")
    o.add_argument("--pdf", required=True)
    o.add_argument("--out", required=True)
    o.add_argument("--dpi", type=int, default=300)
    o.add_argument("--render", action="store_true")
    o.set_defaults(func=_ocr)

    f = sub.add_parser("foot", help="standardize tract footing + exact fractions")
    f.add_argument("--workbook", required=True)
    f.add_argument("--out", required=True)
    f.add_argument("--tracts", required=True, help="comma-separated tract sheet names")
    f.set_defaults(func=_foot)

    q = sub.add_parser("qa", help="formula-error + link + footing scan")
    q.add_argument("--workbook", required=True)
    q.set_defaults(func=_qa)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
