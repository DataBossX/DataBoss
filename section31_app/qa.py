"""QA checks over the assembled workbook data.

Each check returns a QAResult. Severity is one of error/warn/info. The pipeline
records every result on the QA Checks sheet and writes a standalone QA log; a
run with any 'error' result is flagged NOT READY in the completion note.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .ownership import _to_float
from .schema import PRODUCT_SHEETS


@dataclass
class QAResult:
    check: str
    severity: str   # error | warn | info
    result: str     # PASS | WARN | FAIL
    detail: str = ""

    def as_row(self) -> Dict:
        return {"check": self.check, "severity": self.severity,
                "result": self.result, "detail": self.detail}


def run_qa(data: Dict[str, List[Dict]], spend_summary: Dict) -> List[QAResult]:
    results: List[QAResult] = []

    # 1. Product must not be empty.
    product_rows = sum(len(data.get(s, [])) for s in PRODUCT_SHEETS)
    results.append(QAResult(
        "product_not_empty",
        "error" if product_rows == 0 else "info",
        "FAIL" if product_rows == 0 else "PASS",
        f"{product_rows} rows across {', '.join(PRODUCT_SHEETS)}",
    ))

    own = data.get("Tract & Title Ownership", [])

    # 2. Every ownership row should carry a legal description.
    missing_legal = [r for r in own if not r.get("legal_description")]
    results.append(QAResult(
        "ownership_has_legal", "warn" if missing_legal else "info",
        "WARN" if missing_legal else "PASS",
        f"{len(missing_legal)}/{len(own)} ownership rows missing legal description",
    ))

    # 3. OGL number coverage on ownership rows.
    no_ogl = [r for r in own if not r.get("ogl_number")]
    results.append(QAResult(
        "ownership_has_ogl", "warn" if no_ogl else "info",
        "WARN" if no_ogl else "PASS",
        f"{len(no_ogl)}/{len(own)} ownership rows have no OGL number",
    ))

    # 4. Net mineral acres present and positive.
    bad_nma = [r for r in own if _to_float(r.get("net_mineral_acres")) <= 0]
    results.append(QAResult(
        "net_acres_present", "warn" if bad_nma else "info",
        "WARN" if bad_nma else "PASS",
        f"{len(bad_nma)}/{len(own)} ownership rows missing net mineral acres",
    ))

    # 5. WI totals per OGL flagged during normalisation.
    wi = data.get("Leasehold WI Ownership", [])
    wi_flags = [r for r in wi if "!=1.0" in str(r.get("remarks", ""))]
    results.append(QAResult(
        "wi_totals_100", "warn" if wi_flags else "info",
        "WARN" if wi_flags else "PASS",
        f"{len(wi_flags)} WI rows under OGLs that don't total 100%",
    ))

    # 6. Owner addresses present (for notices/leasing).
    no_addr = [r for r in own if not r.get("owner_address")]
    results.append(QAResult(
        "owner_addresses", "info",
        "WARN" if no_addr else "PASS",
        f"{len(no_addr)}/{len(own)} owners without an address on file",
    ))

    # 7. Legal crosswalk matched rate.
    xwalk = data.get("Legal Crosswalk", [])
    matched = [r for r in xwalk if str(r.get("matched")).lower() == "yes"]
    if xwalk:
        rate = 100.0 * len(matched) / len(xwalk)
        results.append(QAResult(
            "legal_crosswalk_rate", "warn" if rate < 60 else "info",
            "WARN" if rate < 60 else "PASS",
            f"{len(matched)}/{len(xwalk)} runsheet legals matched to an OGL "
            f"({rate:.0f}%)",
        ))

    # 8. Spend cap respected.
    over = spend_summary.get("spent_usd", 0) > spend_summary.get("cap_usd", 100)
    results.append(QAResult(
        "image_spend_cap", "error" if over else "info",
        "FAIL" if over else "PASS",
        f"spent ${spend_summary.get('spent_usd',0):.2f} of "
        f"${spend_summary.get('cap_usd',100):.2f} cap",
    ))

    return results


def qa_verdict(results: List[QAResult]) -> str:
    if any(r.result == "FAIL" for r in results):
        return "NOT READY -- errors present"
    if any(r.result == "WARN" for r in results):
        return "READY WITH WARNINGS -- examiner review recommended"
    return "READY"
