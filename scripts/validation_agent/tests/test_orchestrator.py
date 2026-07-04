from pathlib import Path
from core.run_manager import sha256_file
from config.settings import get_settings
from core.orchestrator import Orchestrator

def test_end_to_end_terminates_and_preserves_source(db, audit, sample_workbook, tmp_path, monkeypatch):
    monkeypatch.setenv("DATABOSSX_AGENT_ROOT", str(tmp_path/"agent"))
    (tmp_path/"agent"/"db").mkdir(parents=True, exist_ok=True)
    s = get_settings(reload=True)
    s.outputs_dir = tmp_path/"out"
    before = sha256_file(sample_workbook)
    orch = Orchestrator(s, db, audit)
    # domain context with a clean acreage + no legal facts -> deterministic finish
    result = orch.run(sample_workbook, prospect="FIXTURE",
                      domain_context={"tracts":[
                          {"tract":1,"gross_acres":"637.42","owners":[{"net_acres":"637.42","source_in":"deed"}],"open_balance":"0","conveyances":[]}],
                          "well":{"name":"w","hbp_supported":False}})
    assert result["final_status"] in ("CERTIFY","ESCALATE","MAX_ITERATIONS")
    # source workbook never mutated
    assert sha256_file(sample_workbook) == before
    # exports produced
    assert "markdown" in result["exports"] and "zip" in result["exports"]
    # run finalized in append-only log
    assert audit.final_status(result["run_id"]) == result["final_status"]

def test_dashboard_imports():
    import app.dashboard as d
    assert hasattr(d, "render")
