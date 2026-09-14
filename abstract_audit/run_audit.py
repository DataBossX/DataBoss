"""One-command audit of a local Abstract 4576 working tree.

Walks a root directory, finds every BLM lease PDF, scanned index image,
and section deliverable, runs the index auditor over every workbook,
and prints a single status report with a percent-complete figure.

    python run_audit.py --root "D:/Abstract4576" --json status.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from index_audit import audit_workbook  # noqa: E402
from parity import scan_blm, scan_images  # noqa: E402
from schema import REQUIRED_COLUMNS  # noqa: E402

INDEX_GLOB = "*Abstract_Index*.xlsx"
INDEX_GLOB_ALT = "*Abstract Index*.xlsx"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def collect(root: Path) -> dict[str, list[Path]]:
    buckets: dict[str, list[Path]] = {
        "indexes": [], "checklists": [], "certifications": [],
        "blm_pdfs": [], "images": [],
    }
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name
        low = name.lower()
        if path.suffix.lower() in IMAGE_SUFFIXES:
            buckets["images"].append(path)
        elif low.endswith(".pdf") and low.startswith(("wyw-", "serial register page")):
            buckets["blm_pdfs"].append(path)
        elif "abstract_checklist" in low:
            buckets["checklists"].append(path)
        elif "certification_letter" in low:
            buckets["certifications"].append(path)
        elif "abstract_index" in low or "abstract index" in low:
            if path.suffix.lower() == ".xlsx":
                buckets["indexes"].append(path)
    return buckets


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)

    if not args.root.is_dir():
        ap.error(f"--root {args.root} is not a directory")

    buckets = collect(args.root)
    report: dict[str, object] = {"root": str(args.root)}

    print(f"ROOT: {args.root}")
    print(f"  index workbooks : {len(buckets['indexes'])}")
    print(f"  checklists      : {len(buckets['checklists'])}")
    print(f"  certifications  : {len(buckets['certifications'])}")
    print(f"  BLM pdfs        : {len(buckets['blm_pdfs'])}")
    print(f"  images          : {len(buckets['images'])}")

    series, srps = scan_blm([p.name for p in buckets["blm_pdfs"]])
    incomplete = {k: v.missing_parts for k, v in series.items() if not v.complete}
    report["blm"] = {
        "leases": len(series),
        "lease_document_pdfs": sum(s.file_count for s in series.values()),
        "incomplete_series": incomplete,
        "leases_without_srp": sorted(set(series) - set(srps)),
    }
    print(f"\nBLM: {len(series)} leases, "
          f"{sum(s.file_count for s in series.values())} part PDFs")
    for lease, missing in incomplete.items():
        print(f"  MISSING {lease}: parts {missing}")

    report["images"] = scan_images([p.name for p in buckets["images"]])
    for section, info in report["images"].items():
        if section == "_unparsed":
            continue
        print(f"IMAGES section {section}: {info['count']} "
              f"({info['first']}..{info['last']}) missing={info['missing']}")

    index_reports, total_req, filled_req = [], 0, 0
    for wb_path in sorted(buckets["indexes"]):
        try:
            rep = audit_workbook(wb_path)
        except Exception as exc:  # noqa: BLE001 - report, never abort the sweep
            print(f"  ERROR {wb_path.name}: {exc}")
            index_reports.append({"path": str(wb_path), "error": str(exc)})
            continue
        for name, stat in rep.columns.items():
            if name in REQUIRED_COLUMNS:
                total_req += stat.filled + stat.blank
                filled_req += stat.filled
        index_reports.append(rep.to_dict())
        print(f"  {wb_path.name}: rows={rep.row_count} "
              f"required={rep.completeness:.1%} "
              f"blanks={len(rep.blank_required)} dupes={len(rep.duplicate_doc_nos)}")

    report["indexes"] = index_reports
    pct = 1.0 if total_req == 0 else filled_req / total_req
    report["overall_required_completeness"] = round(pct, 4)
    print(f"\nOVERALL required-cell completeness: {pct:.2%} "
          f"({filled_req}/{total_req} cells)")

    if args.json:
        args.json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
