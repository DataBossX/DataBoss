"""Report finder / improver / output generator: scoring, no-overwrite, no fabrication."""
from pathlib import Path

from reports.report_finder import ReportFinder
from reports.report_improver import ReportImprover
from reports.output_generator import OutputGenerator


def test_report_finder_scores_and_picks_best(tmp_path):
    good = tmp_path / "31-12n-24w_cursory_title_report.md"
    good.write_text("# Cursory Title Report\nTract 1 OGL working interest chain curative source Bk 1736/0592",
                    encoding="utf-8")
    noise = tmp_path / "notes.txt"
    noise.write_text("random content", encoding="utf-8")
    best = ReportFinder([str(tmp_path)]).best()
    assert best is not None
    assert Path(best.path).name == good.name
    assert best.score > 0


def test_output_generator_never_overwrites(tmp_path):
    outg = OutputGenerator(tmp_path)
    a = outg.write_markdown("one", "audit_report.md")
    b = outg.write_markdown("two", "audit_report.md")
    assert a != b
    assert a.exists() and b.exists()
    assert a.read_text() == "one" and b.read_text() == "two"


def test_report_improver_versioned_and_labels_only(tmp_path):
    imp = ReportImprover(tmp_path)

    class R:  # duck-typed validation result
        gate_name = "Acreage Footing Gate"; status = "FAIL"; severity = "HIGH"
        repairable = False; reason = "Over-conveyance of 15 NMA"
    out1 = imp.improve(best_report=None, manifest={"file_name": "wb.xlsx", "file_sha256": "abc"},
                       validation_results=[R()], source_summary={"total": 3, "found_local": 1, "missing": 2},
                       escalations=[{"category": "Title Chain Gap", "subject": "Tract 2",
                                     "detail": "gap", "recommended_action": "examiner"}],
                       final_state="ESCALATE", mode="dry-run",
                       spend={"cumulative": "0.00", "cap": "100.00", "remaining": "100.00"})
    out2 = imp.improve(best_report=None, manifest={"file_name": "wb.xlsx", "file_sha256": "abc"},
                       validation_results=[R()], source_summary={"total": 3, "found_local": 1, "missing": 2},
                       escalations=[], final_state="ESCALATE", mode="dry-run",
                       spend={"cumulative": "0.00", "cap": "100.00", "remaining": "100.00"})
    assert out1 != out2  # versioned, never overwritten
    text = out1.read_text()
    assert "Validation Scorecard" in text
    # Missing sources labelled, not invented
    assert "never invented" in text
    assert "BLOCKED BY MISSING CREDENTIALS" in text


def test_missing_docs_and_matrix(tmp_path):
    outg = OutputGenerator(tmp_path)
    miss = outg.write_missing_docs([{"reference": "1736/0592", "kind": "book_page",
                                     "sheet": "OGL", "cell": "C2", "status": "missing"}])
    assert "1736/0592" in miss.read_text()
    matrix = outg.write_escalation_matrix([{"category": "HBP Unsupported", "subject": "well",
                                            "detail": "per recital", "recommended_action": "OCC"}])
    assert "HBP Unsupported" in matrix.read_text()
