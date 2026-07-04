from pathlib import Path
from reports.report_finder import find_reports, best_report
from reports.report_improver import improve_report

def test_finder_scores_and_ranks(tmp_path):
    (tmp_path/"a.md").write_text("Tract 1 OGL working interest chain HBP book 1736/0594 instrument 2021-001068")
    (tmp_path/"b.txt").write_text("unrelated content")
    reports = find_reports([tmp_path])
    assert reports[0]["path"].endswith("a.md")
    assert reports[0]["has_sources"] is True

def test_improver_writes_new_file_no_overwrite(tmp_path):
    best = {"path": str(tmp_path/"src.md")}
    Path(best["path"]).write_text("# base report\nTract data (FIXTURE)")
    ctx = {"run_id":"r","prospect":"P","gate_results":[
        {"gate_name":"G","status":"ESCALATE","severity":"HIGH","affected_subject":"s","repairable":False}],
        "source_documents":[{"book_page":"1736/0594","status":"blocked","detail":"dry"}],
        "escalations":[{"subject":"x","reason":"y","needed_document":"1736/0594"}],
        "final_status":"ESCALATE"}
    out = tmp_path/"improved.md"
    improve_report(best, ctx, out)
    assert out.exists()
    assert "VERIFIED" in out.read_text()  # labels present
    assert "# base report" in out.read_text()  # base included verbatim
