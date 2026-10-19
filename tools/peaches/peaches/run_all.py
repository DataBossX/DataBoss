"""Orchestrate a full PEACHES run over a folder tree.

Steps executed: inventory -> boundary detection -> vision queue ->
index_qa for every workbook found -> donor_compare (with --donor) ->
run_summary.md listing counts and every finding. The summary reports
what was executed and what was found; it does not certify anything.

CLI: python -m peaches.run_all <root> <outdir> [--donor <workbook>]
"""
from __future__ import annotations

import argparse
import os
import sys

from . import boundaries, donor_compare, index_qa, inventory, vision_queue


def run_all(root, outdir, donor=None):
    root = os.path.abspath(root)
    os.makedirs(outdir, exist_ok=True)
    summary = inventory.run_inventory(root, outdir)
    inv_csv = os.path.join(outdir, "inventory.csv")
    bnd_csv = os.path.join(outdir, "boundaries.csv")
    boundaries.run_boundaries(root, bnd_csv)
    queue = vision_queue.build_queue(inv_csv, bnd_csv)
    import csv as _csv
    with open(os.path.join(outdir, "vision_queue.csv"), "w", newline="",
              encoding="utf-8") as fh:
        writer = _csv.DictWriter(fh, fieldnames=vision_queue.FIELDS)
        writer.writeheader()
        writer.writerows(queue)

    qa_results = []
    comparisons = []
    for row in summary["files"]:
        if row["ext"] not in (".ods", ".xlsx"):
            continue
        path = os.path.join(root, row["path"])
        try:
            result = index_qa.qa_workbook(path)
        except Exception as exc:
            result = {"file": row["name"], "kind": "unreadable",
                      "data_row_count": 0,
                      "findings": [{"severity": "HIGH", "check": "READ_ERROR",
                                    "row": "", "col": "",
                                    "detail": "%s: %s" % (type(exc).__name__, exc)}]}
        index_qa.write_outputs(result, outdir) \
            if "census" in result else None
        qa_results.append(result)
        if donor:
            try:
                comp = donor_compare.compare(path, donor)
                comparisons.append((row["name"], comp))
            except Exception as exc:
                comparisons.append((row["name"], {"error": "%s: %s"
                                        % (type(exc).__name__, exc)}))

    lines = []
    lines.append("# PEACHES run summary")
    lines.append("")
    lines.append("Root: `%s`" % root)
    lines.append("")
    lines.append("## Counts (measured by the checks that ran)")
    lines.append("")
    lines.append("- Files inventoried: %d (%d PDFs, %d workbooks)"
                 % (summary["file_count"], summary["pdf_count"],
                    summary["workbook_count"]))
    lines.append("- PDF pages total: %d" % summary["pdf_pages_total"])
    lines.append("- Workbooks QA-checked: %d" % len(qa_results))
    lines.append("- Pages in vision queue: %d" % len(queue))
    total_findings = sum(len(r["findings"]) for r in qa_results)
    lines.append("- Index QA findings recorded: %d" % total_findings)
    lines.append("")
    lines.append("## Per-workbook results")
    for r in qa_results:
        lines.append("")
        lines.append("### %s" % r["file"])
        lines.append("- Kind detected: %s; data rows: %s; findings: %d"
                     % (r.get("kind"), r.get("data_row_count"),
                        len(r["findings"])))
        if "census" in r:
            lines.append("- UNKNOWN cells: %d exact, %d qualified"
                         % (r["unknown_total"], r["unknown_qualified_total"]))
            lines.append("- Duplicates: %s; near-duplicates: %s"
                         % (r["duplicates"], r["near_duplicates"]))
            lines.append("- Comments violations: %d; date violations: %d"
                         % (r["comments_violations"], r["date_violations"]))
    if donor:
        lines.append("")
        lines.append("## Donor comparisons (parser-level)")
        for name, comp in comparisons:
            if "error" in comp:
                lines.append("- %s: comparison error %s" % (name, comp["error"]))
                continue
            agrees = sum(1 for p in comp["properties"].values()
                         if p["status"] == "AGREES")
            lines.append("- %s vs donor: %d/%d properties AGREE"
                         % (name, agrees, len(comp["properties"])))
            for prop, p in comp["properties"].items():
                if p["status"] == "DIFFERS":
                    lines.append("  - DIFFERS %s: candidate=%r donor=%r"
                                 % (prop, p["candidate"], p["donor"]))
    lines.append("")
    lines.append("## Findings")
    if total_findings == 0:
        lines.append("- None recorded by the checks that ran.")
    for r in qa_results:
        for f in r["findings"]:
            lines.append("- [%s] %s %s (row %s): %s"
                         % (f["severity"], r["file"], f["check"],
                            f["row"] or "-", f["detail"]))
    lines.append("")
    lines.append("Boundaries listed in boundaries.csv are CANDIDATEs. "
                 "Pages in vision_queue.csv have not been reviewed. "
                 "This summary reports executed checks only.")
    with open(os.path.join(outdir, "run_summary.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return {"inventory": summary, "qa_results": qa_results,
            "vision_queue": queue, "comparisons": comparisons}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="peaches.run_all")
    parser.add_argument("root")
    parser.add_argument("outdir")
    parser.add_argument("--donor", default=None)
    args = parser.parse_args(argv)
    result = run_all(args.root, args.outdir, donor=args.donor)
    print("run_all: %d files, %d workbooks QA-checked, %d findings -> %s"
          % (result["inventory"]["file_count"], len(result["qa_results"]),
             sum(len(r["findings"]) for r in result["qa_results"]),
             args.outdir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
