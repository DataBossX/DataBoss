"""qa_auditor plugin — wraps the existing DataBossX QA auditor.

The auditor is the Horizon validation gate that already ships in this repo:

* ``horizon.validation`` — interest reconciliation, schema gates, Golden
  Source instrument/column checks. Validation NEVER fabricates data.
* ``horizon.models``     — the typed report contract (pydantic).

This plugin WRAPS those originals (per the absorb mandate: wrap, do not
rewrite). Every entrypoint takes a JSON payload dict and returns a JSON-able
dict, matching the Foundry plugin contract.

Requires ``pydantic>=2`` (declared in plugin.json requires.python).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from horizon.models import ReportModel, TitleRow  # noqa: E402
from horizon.validation import load_requirements, validate_report  # noqa: E402


def _build_report(rows: List[Dict[str, Any]], section: str, source: str) -> ReportModel:
    return ReportModel(section=section, source=source,
                       rows=[TitleRow(**row) for row in rows])


def audit_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate report rows against the Golden Source (or built-in defaults).

    payload: {"rows": [ {TitleRow fields...}, ... ],
              "section": optional str (report provenance, default "adhoc"),
              "source": optional str,
              "golden_path": optional str path to project_notes_updated.xlsx}
    """
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("audit_report payload requires 'rows': a list of row objects")
    report = _build_report(
        rows,
        section=str(payload.get("section", "adhoc")),
        source=str(payload.get("source", "qa_auditor plugin")),
    )
    golden = payload.get("golden_path")
    requirements = load_requirements(Path(golden) if golden else None)
    result = validate_report(report, requirements)
    return {
        "ok": True,
        "passed": result.passed,
        "summary": result.summary(),
        "requirements_source": requirements.source,
        "issues": [
            {
                "row_index": issue.row_index,
                "field": issue.field,
                "severity": issue.severity,
                "message": issue.message,
            }
            for issue in result.issues
        ],
    }


def smoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Self-test: a clean row passes; a bad interest row raises an issue."""
    clean = audit_report({
        "rows": [{
            "entry_no": "1",
            "grantor": "Alice Doe",
            "grantee": "Bob Roe",
            "instrument_number": "2024-001",
            "legal_description": "NW/4 Sec 1-T10N-R20W",
            "conveyed_interest": "1/2",
            "retained_interest": "1/2",
        }],
    })
    dirty = audit_report({
        "rows": [{
            "entry_no": "2",
            "grantor": "Alice Doe",
            "grantee": "Bob Roe",
            "instrument_number": "2024-002",
            "legal_description": "NW/4 Sec 1-T10N-R20W",
            "conveyed_interest": "3/4",
            "retained_interest": "1/2",
        }],
    })
    ok = clean["passed"] and not dirty["passed"] and len(dirty["issues"]) > 0
    return {
        "ok": ok,
        "clean_case": {"passed": clean["passed"], "summary": clean["summary"]},
        "dirty_case": {
            "passed": dirty["passed"],
            "summary": dirty["summary"],
            "first_issue": dirty["issues"][0] if dirty["issues"] else None,
        },
    }
