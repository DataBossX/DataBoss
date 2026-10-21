"""chqa command line. One machine-readable JSON report per section."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

from . import discover as discover_mod
from . import profile as profile_mod
from .checks_content import check_content
from .checks_format import check_format
from .checks_letter import check_letter
from .checks_package import check_zip, required_client_files
from .checks_parity import check_parity
from .checks_pdf import check_pdf
from .conform import conform
from .findings import Report
from .readers import read_workbook
from .render import compare_renders, to_pdf


def _date(s: str | None):
    return dt.date.fromisoformat(s) if s else None


def _load(p: str) -> dict:
    return json.load(open(p, encoding="utf8"))


def cmd_profile(a) -> int:
    return profile_mod.main([a.donor, "-o", a.out, "--kind", a.kind])


def cmd_check(a) -> int:
    prof = _load(a.profile)
    fmt, cont = Report("format"), Report("content")
    sh = check_format(a.workbook, prof, fmt, a.sheet)
    check_content(a.workbook, sh, prof, cont, kind=prof["kind"], posted_thru=_date(a.posted_thru),
                  links_csv=a.links, expected_file_no=a.file_no)
    pf, pc = fmt.write(a.out), cont.write(a.out)
    print(f"format: {fmt.errors} errors -> {pf}\ncontent: {cont.errors} errors -> {pc}")
    return 1 if (fmt.errors or cont.errors) else 0


def cmd_parity(a) -> int:
    rep = Report("parity")
    check_parity(a.a, a.b, rep)
    print(f"parity: {rep.errors} errors -> {rep.write(a.out)}")
    return 1 if rep.errors else 0


def cmd_pdf(a) -> int:
    rep = Report("pdf")
    sheet = read_workbook(a.workbook).sheets[0] if a.workbook else None
    check_pdf(a.pdf, rep, expect_orientation=a.orientation, expect_pages=a.pages, sheet=sheet,
              margins_in=tuple(a.margins) if a.margins else None)
    print(f"pdf: {rep.errors} errors -> {rep.write(a.out)}")
    return 1 if rep.errors else 0


def cmd_letter(a) -> int:
    rep = Report("letter")
    check_letter(a.docx, a.donor, rep, prepared=_date(a.prepared), posted_thru=_date(a.posted_thru))
    print(f"letter: {rep.errors} errors -> {rep.write(a.out)}")
    return 1 if rep.errors else 0


def cmd_package(a) -> int:
    rep = Report("package")
    info = check_zip(a.zip, rep, required=required_client_files(a.section, a.blm or []), expected_sha=a.sha256)
    path = rep.write(a.out)
    json.dump(info, open(os.path.join(a.out, "package_manifest.json"), "w"), indent=2)
    print(f"package: {rep.errors} errors, sha256={info['sha256']} -> {path}")
    return 1 if rep.errors else 0


def cmd_render(a) -> int:
    rep = Report("render")
    import shutil as _sh
    from .odsfix import set_ods_paper
    pdf_dir = os.path.join(a.out, "pdf")
    os.makedirs(pdf_dir, exist_ok=True)
    work = {}
    for tag, src in (("candidate", a.candidate), ("donor", a.donor)):      # renders use COPIES; sources untouched
        dst = os.path.join(pdf_dir, f"{tag}_{os.path.basename(src)}")
        _sh.copyfile(src, dst)
        if dst.lower().endswith(".ods") and set_ods_paper(dst):
            rep.inputs.setdefault("paper_normalized", []).append(tag)
        work[tag] = dst
    cand, donor = to_pdf(work["candidate"], pdf_dir), to_pdf(work["donor"], pdf_dir)
    if not (cand and donor):
        rep.skipped.append("LibreOffice unavailable: no render performed (no parity claim made)")
        print("render skipped:", rep.write(a.out))
        return 2
    res = compare_renders(cand, donor, os.path.join(a.out, "png"), rep, pages=a.pages, threshold=a.threshold)
    rep.inputs["renderer"] = "LibreOffice headless (NOT Microsoft Office)"
    rep.inputs["pages"] = res
    print(f"render: {rep.errors + len(rep.findings)} findings -> {rep.write(a.out)}")
    return 0


def cmd_conform(a) -> int:
    prof = _load(a.profile)
    meta = {}
    for kv in a.set or []:
        k, v = kv.split("=", 1)
        meta[k] = dt.date.fromisoformat(v) if v[:4].isdigit() and "-" in v and len(v) == 10 else v
    rep = conform(a.source, prof, a.out_xlsx, sheet_name=a.sheet, font_size=a.font_size, metadata=meta)
    print(f"candidate: {rep['xlsx']}  ods: {rep['ods']}  changes={len(rep['changes'])}  needs_human={len(rep['needs_human'])}")
    return 0


def cmd_discover(a) -> int:
    return discover_mod.main([a.listing, "--sections", *a.sections, "-o", a.out] + (["--me", a.me] if a.me else []) +
                             (["--since", a.since] if a.since else []))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="chqa", description="Combine-Harvest donor-format QA toolkit")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("profile"); p.add_argument("donor"); p.add_argument("-o", "--out", required=True); p.add_argument("--kind", default="index", choices=["index", "blm"]); p.set_defaults(fn=cmd_profile)
    p = sub.add_parser("check"); p.add_argument("workbook"); p.add_argument("--profile", required=True); p.add_argument("--out", required=True)
    p.add_argument("--posted-thru"); p.add_argument("--links"); p.add_argument("--file-no"); p.add_argument("--sheet"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("parity"); p.add_argument("a"); p.add_argument("b"); p.add_argument("--out", required=True); p.set_defaults(fn=cmd_parity)
    p = sub.add_parser("pdf"); p.add_argument("pdf"); p.add_argument("--workbook"); p.add_argument("--orientation"); p.add_argument("--pages", type=int)
    p.add_argument("--margins", type=float, nargs=4, metavar=("TOP", "BOTTOM", "LEFT", "RIGHT")); p.add_argument("--out", required=True); p.set_defaults(fn=cmd_pdf)
    p = sub.add_parser("letter"); p.add_argument("docx"); p.add_argument("--donor", required=True); p.add_argument("--prepared"); p.add_argument("--posted-thru"); p.add_argument("--out", required=True); p.set_defaults(fn=cmd_letter)
    p = sub.add_parser("package"); p.add_argument("zip"); p.add_argument("--section", required=True); p.add_argument("--blm", nargs="*"); p.add_argument("--sha256"); p.add_argument("--out", required=True); p.set_defaults(fn=cmd_package)
    p = sub.add_parser("render"); p.add_argument("candidate"); p.add_argument("--donor", required=True); p.add_argument("--out", required=True); p.add_argument("--pages", type=int, default=3); p.add_argument("--threshold", type=float, default=0.02); p.set_defaults(fn=cmd_render)
    p = sub.add_parser("conform"); p.add_argument("source"); p.add_argument("--profile", required=True); p.add_argument("--out-xlsx", required=True)
    p.add_argument("--sheet"); p.add_argument("--font-size", type=float, default=11.0); p.add_argument("--set", nargs="*", help='metadata, e.g. "Date:=2026-10-20"'); p.set_defaults(fn=cmd_conform)
    p = sub.add_parser("discover"); p.add_argument("listing"); p.add_argument("--sections", nargs="+", required=True); p.add_argument("--me"); p.add_argument("--since"); p.add_argument("-o", "--out", required=True); p.set_defaults(fn=cmd_discover)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
