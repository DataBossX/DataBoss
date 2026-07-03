"""CLI entry point.  python -m titlefinisher <offline|online|worklist|audit> [flags]"""
from __future__ import annotations
import argparse, glob, os, sys, json
from .config import Config
from .pipeline import run_offline, run_online
from .workbook.reader import build_worklist, worklist_summary
from .workbook.auditor import audit


def _autofind(pattern, root):
    hits = glob.glob(os.path.join(root, pattern))
    return hits[0] if hits else None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="titlefinisher", description=__doc__)
    ap.add_argument("mode", choices=["offline", "online", "worklist", "audit"])
    ap.add_argument("--workbook", help="path to the NHE cursory workbook (.xlsx)")
    ap.add_argument("--index", help="path to the county index PDF")
    ap.add_argument("--baseline", help="baseline workbook for audit mode")
    ap.add_argument("--outdir", default="data/out")
    ap.add_argument("--county"); ap.add_argument("--twprge"); ap.add_argument("--section")
    args = ap.parse_args(argv)

    cfg = Config()
    if args.county: cfg.county = args.county
    if args.twprge: cfg.twprge = args.twprge
    if args.section: cfg.section = args.section

    wb = args.workbook or _autofind("*NHE*.xlsx", "data") or _autofind("*.xlsx", "data")
    if args.mode in ("offline", "online", "worklist") and not wb:
        sys.exit("No workbook found. Pass --workbook or put one in ./data/")

    if args.mode == "worklist":
        items = build_worklist(wb)
        print(json.dumps(worklist_summary(items), indent=2))
        for it in items:
            print(f"  {it.kind:14} {it.sheet}!{it.coord}  {it.party or it.instrument or it.detail[:40]}")
        return
    if args.mode == "audit":
        base = args.baseline or wb
        ok, issues, notes = audit(base, wb)
        print("AUDIT:", "PASS" if ok else "ISSUES")
        for n in notes: print("  ok  ", n)
        for i in issues: print("  !!  ", i)
        sys.exit(0 if ok else 1)

    idx = args.index or _autofind("*Index*.pdf", "data") or _autofind("*.pdf", "data")
    if args.mode == "offline":
        res = run_offline(wb, idx, args.outdir, cfg)
    else:
        res = run_online(wb, args.outdir, cfg)
    print(json.dumps({k: v for k, v in res.items() if k != "worklist"}, indent=2, default=str))
    print("worklist:", res.get("worklist"))


if __name__ == "__main__":
    main()
