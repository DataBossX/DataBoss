"""End-to-end example build for the Roger Mills 31-12N-24W job.

Wires the pipeline: repair footing -> add Index Evidence -> QA. Driven by the
section geometry in config; reusable for other sections by changing the geometry.
Run:  python -m title_report_builder.report.build_roger_mills SRC.xlsx OUT.xlsx EVIDENCE.json
"""
from __future__ import annotations
import json
import sys

from ..config import BuildConfig
from .title_logic import Instrument, assign_tracts, dedupe
from .workbook_builder import repair_all_tracts, add_index_evidence
from .qa import scan

ROGER_MILLS_31 = {
    1: ["NE NE", "NW NE"],
    2: ["SW NE", "NW SE", "SW SE", "SE SE"],
    3: ["SE NE"],
    4: ["NE NW", "SE NW"],
    5: ["NW NW", "SW NW", "SE SW"],
    6: ["NW SW", "SW SW"],
    7: ["NE SW"],
    8: ["NE SE"],
}


def build(src_xlsx: str, out_xlsx: str, evidence_json: str | None = None) -> dict:
    cfg = BuildConfig(project_dir=".", tract_aliquots=ROGER_MILLS_31)
    tract_sheets = [f"Tract {i}" for i in range(1, 9)]

    repair = repair_all_tracts(src_xlsx, tract_sheets, out_xlsx)

    n_ev = 0
    if evidence_json:
        records = json.load(open(evidence_json))
        insts = [Instrument.from_record(r) for r in records
                 if not r.get("uncertain") and (r.get("grantor") or r.get("grantee"))]
        assign_tracts(insts, cfg.aliquot_to_tract())
        insts = dedupe(insts)
        insts.sort(key=lambda x: x.date or "")
        n_ev = add_index_evidence(out_xlsx, insts, out_xlsx)

    rep = scan(out_xlsx)
    return {
        "footing": {k: v["foots"] for k, v in repair["tracts"].items()},
        "fractions_replaced": repair["fractions_replaced"],
        "index_evidence_rows": n_ev,
        "qa_passed": rep.passed,
        "cached_errors": rep.cached_errors,
    }


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    ev = sys.argv[3] if len(sys.argv) > 3 else None
    print(json.dumps(build(src, out, ev), indent=2))
