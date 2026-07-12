import json
from pathlib import Path

from databoss_title_factory.cli import build_parser


ROOT = Path(__file__).parents[1]
LAUNCHERS = {
    "SETUP_DATABOSS_TITLE_INTELLIGENCE.bat",
    "START_DATABOSS_TITLE_INTELLIGENCE.bat",
    "STOP_DATABOSS_TITLE_INTELLIGENCE.bat",
    "OPEN_DATABOSS_TITLE_INTELLIGENCE.bat",
    "RUN_SECTION32_PIPELINE.bat",
    "RUN_SOURCE_INVENTORY.bat",
    "RUN_OCR_PIPELINE.bat",
    "RUN_TEMPLATE_QA.bat",
    "BACKUP_DATABOSS_TITLE_INTELLIGENCE.bat",
    "HEALTH_CHECK_DATABOSS_TITLE_INTELLIGENCE.bat",
}
DOCS = {
    "README.md",
    "docs/architecture/SYSTEM_ARCHITECTURE.md",
    "docs/architecture/DATA_MODEL.md",
    "docs/architecture/PROCESSING_PIPELINE.md",
    "docs/security/SECURITY_MODEL.md",
    "docs/security/THREAT_MODEL.md",
    "docs/security/SECRETS_AND_PROVIDERS.md",
    "docs/operations/INSTALL_WINDOWS.md",
    "docs/operations/START_STOP_BACKUP.md",
    "docs/operations/SECTION32_RUNBOOK.md",
    "docs/operations/RECOVERY.md",
    "docs/title-methodology/TITLE_EXAMINATION_RULES.md",
    "docs/title-methodology/LEASEHOLD_CALCULATIONS.md",
    "docs/title-methodology/EVIDENCE_STANDARDS.md",
    "docs/user/USER_GUIDE.md",
    "docs/user/REVIEWER_GUIDE.md",
    "docs/developer/DEVELOPMENT.md",
    "docs/developer/TESTING.md",
}


def _launcher(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8").lower()


def test_required_windows_launchers_exist_and_resolve_repository_root():
    assert all((ROOT / name).is_file() for name in LAUNCHERS)
    assert all('cd /d "%~dp0"' in _launcher(name) for name in LAUNCHERS)
    setup = _launcher("SETUP_DATABOSS_TITLE_INTELLIGENCE.bat")
    assert ".venv" in setup and "pip install" in setup and ".runtime\\logs" in setup


def test_app_launchers_enforce_loopback_pid_and_recorded_pid_only():
    start = _launcher("START_DATABOSS_TITLE_INTELLIGENCE.bat")
    stop = _launcher("STOP_DATABOSS_TITLE_INTELLIGENCE.bat")
    opened = _launcher("OPEN_DATABOSS_TITLE_INTELLIGENCE.bat")
    assert "127.0.0.1" in start
    assert "databoss-title-intelligence.pid" in start
    assert "already running" in start
    assert "get-ciminstance" in start and "commandline" in start
    assert "databoss-title-intelligence.pid" in stop
    assert "stop-process -id" in stop
    assert "get-ciminstance" in stop and "commandline" in stop
    assert "taskkill" not in stop and "stop-process -name" not in stop
    assert "127.0.0.1:8501" in opened


def test_pipeline_launchers_map_to_real_cli_and_backup_excludes_source_corpus():
    expected = {
        "RUN_SOURCE_INVENTORY.bat": " inventory ",
        "RUN_OCR_PIPELINE.bat": " ocr ",
        "RUN_SECTION32_PIPELINE.bat": " pipeline ",
        "RUN_TEMPLATE_QA.bat": " template-qa ",
        "HEALTH_CHECK_DATABOSS_TITLE_INTELLIGENCE.bat": " health",
    }
    for name, command in expected.items():
        text = _launcher(name)
        assert ".venv\\scripts\\python.exe" in text
        assert "-m databoss_title_factory" in text
        assert command in text
        assert ".runtime\\logs" in text
    backup = _launcher("BACKUP_DATABOSS_TITLE_INTELLIGENCE.bat")
    assert "databoss_title_factory_output" in backup
    assert "compress-archive" in backup
    assert "source corpus was copied" in backup
    assert "compress-archive -literalpath $items" in backup


def test_cli_serve_and_ocr_parser_contract():
    parser = build_parser()
    ocr = parser.parse_args(["ocr", "--root", "evidence", "--allow-root", "evidence"])
    assert ocr.command == "ocr" and ocr.weak_threshold == 0.65
    serve = parser.parse_args(
        [
            "serve",
            "--auth-database",
            "auth.sqlite3",
            "--allow-root",
            ".",
            "--port",
            "8501",
        ]
    )
    assert serve.command == "serve" and serve.port == 8501


def test_requested_docs_and_truthful_completion_schema_exist():
    assert all((ROOT / path).is_file() for path in DOCS)
    completion = json.loads((ROOT / "completion.json").read_text(encoding="utf-8"))
    assert completion["schema_version"] == "1.0"
    assert completion["final_status"] == "PASS_WITH_DISCLOSED_LIMITATIONS"
    assert completion["source_inventory_status"] == "BLOCKED_SOURCE_NOT_MOUNTED"
    assert completion["commit"] == "PENDING_COMMIT"
    assert "SYNTHETIC_TESTED" in completion["ocr_status"]
    assert "UNPROCESSED" in completion["tract_chain_status"]
    assert "UNCALCULATED" in completion["wi_nri_status"]
    assert "NOT_PRODUCED" in completion["report_generator_status"]
    assert (ROOT / "IMPLEMENTATION_REPORT.md").is_file()
