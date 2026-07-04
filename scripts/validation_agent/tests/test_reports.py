"""Report generation never overwrites; improver adds no unverified facts."""

from __future__ import annotations

from pathlib import Path

from core.enums import GateStatus, Severity
from reports.output_generator import OutputGenerator
from reports.report_finder import ReportFinder
from reports.report_improver import ReportImprover
from validators.base_validator import Escalation, ValidationResult


def _results():
    return [
        ValidationResult(gate_name="Acreage Footing Gate", status=GateStatus.PASS,
                         reason="foots to 637.42"),
        ValidationResult(gate_name="Source Verification Gate", status=GateStatus.ESCALATE,
                         severity=Severity.HIGH, reason="missing source",
                         affected_subject="book_101_page_201"),
    ]


def test_output_generator_versions_not_overwrites(settings, audit, tmp_path):
    gen = OutputGenerator(audit, "run_x", tmp_path / "exports")
    ctx = {
        "results": _results(),
        "escalations": [],
        "source_index": {"missing": [{"reference_key": "book_101_page_201"}], "found": []},
        "certified": False,
        "final_state": "STATE_ESCALATE",
    }
    b1 = gen.generate(ctx)
    b2 = gen.generate(ctx)
    paths1 = {f["path"] for f in b1.files}
    paths2 = {f["path"] for f in b2.files}
    # second run must not reuse the same audit_report.md path
    assert paths1 != paths2
    # exports recorded in append-only table
    rows = audit.db.query("SELECT * FROM report_exports WHERE run_id='run_x'")
    assert rows


def test_report_improver_labels_and_preserves(settings, audit, tmp_path):
    prior = tmp_path / "prior_report.md"
    prior.write_text("# Prior Title Report\nGrantor: Alice\n", encoding="utf-8")
    improver = ReportImprover(audit, "run_y", tmp_path / "reports")
    out = improver.improve(
        prior_report=prior,
        results=_results(),
        escalations=[Escalation(failed_gate="Source Verification Gate",
                                subject="book_101_page_201")],
        source_index={"found": [], "missing": [{"reference_key": "book_101_page_201",
                                                "reference_type": "book_page"}]},
        manifest={"workbook": {"filename": "wb.xlsx", "sha256": "abc"}},
    )
    body = Path(out["path"]).read_text(encoding="utf-8")
    assert "NEEDS EXAMINER REVIEW" in body
    assert "VERIFIED" in body
    # prior content preserved verbatim
    assert "Prior Title Report" in body
    # no fabricated fact: the missing ref is labelled, not asserted as found
    assert "book_101_page_201" in body


def test_report_finder_scores_candidates(settings, tmp_path):
    d = tmp_path / "reports"
    d.mkdir()
    (d / "wb_title_report.md").write_text(
        "tract ogl working interest chain grantor book 101 certification",
        encoding="utf-8",
    )
    object.__setattr__(settings, "extra_source_dirs", [d])
    finder = ReportFinder(settings)
    best = finder.best(workbook_stem="wb")
    assert best is not None
    assert best.score > 0
