"""Traceability & no-fabrication verifier (an automated QA gate).

Encodes mission non-negotiables #3 (every fact traceable to a source) and #4
(low confidence must be flagged, not guessed). Reads the pipeline outputs and
reports violations; exits non-zero if any high-severity violation is found, so
it can gate a release.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from report_pipeline import common as C

HIGH_VALUE = {"decimal_interest", "net_acres", "royalty", "net_revenue_interest",
              "working_interest", "legal_description"}


def verify(out: Path) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []

    def add(check, severity, ref, detail):
        violations.append({"check": check, "severity": severity, "ref": ref,
                           "detail": detail, "generated_at": C.now_iso()})

    inventory = C.read_csv(out / "file_inventory.csv")
    facts = C.read_csv(out / "extracted_facts.csv")
    inv_paths = {r["path"] for r in inventory}

    for f in facts:
        ref = f.get("relpath", "")
        src = f.get("source_file", "")
        if not src:
            add("fact_missing_source", "high", ref, "fact row has no source_file")
        elif src not in inv_paths:
            add("source_not_in_inventory", "high", ref, f"source_file not in inventory: {src}")

        # High-value fields must not be populated at low confidence without a flag.
        try:
            conf = float(f.get("confidence") or 0)
        except ValueError:
            conf = 0.0
        flags = (f.get("review_flags") or "")
        for hv in HIGH_VALUE:
            if f.get(hv) and conf < 0.6 and "low_conf" not in flags and "REVIEW" not in flags:
                add("high_value_low_conf_unflagged", "high", ref,
                    f"{hv} populated at conf {conf} without a review flag")

    # review_required rows should all be high severity (sanity on the gate itself)
    for r in C.read_csv(out / "review_required.csv"):
        if r.get("severity") and r["severity"] != "high":
            add("review_required_wrong_severity", "low", r.get("relpath", ""),
                f"severity={r.get('severity')}")

    C.write_table(out, "traceability_report",
                  ["check", "severity", "ref", "detail", "generated_at"], violations)
    return violations


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="verify-traceability", description="Traceability/no-fabrication gate")
    ap.add_argument("--root", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    root = C.resolve_root(args.root)
    out = C.output_dir(root, args.out)
    log = C.get_logger("verify", out=out)
    violations = verify(out)
    high = [v for v in violations if v["severity"] == "high"]
    log.info("traceability: %d violations (%d high)", len(violations), len(high))
    for v in high[:20]:
        log.warning("VIOLATION %s | %s | %s", v["check"], v["ref"], v["detail"])
    return 1 if high else 0


if __name__ == "__main__":
    raise SystemExit(main())
