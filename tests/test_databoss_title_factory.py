import json
from pathlib import Path

import openpyxl
from PIL import Image, ImageDraw

from databoss_title_factory.core import (
    OUTPUT_DIR_NAME,
    build_inventory,
    build_runsheet,
    export_safe_xlsx,
    extract_and_reconcile,
    preprocess_images,
    run_ocr,
    start_run,
    tournament_reconcile,
)


def _source_text() -> str:
    return """
Instrument Number: 2026-001234
Warranty Deed
Instrument Date: 01/02/2026
Recorded Date: 01/05/2026
Grantor: Ada Owner
Grantee: Beacon Minerals LLC
Book: 44
Page: 219
Legal Description: NE/4 Section 31, Township 12 North, Range 24 West
Interest Conveyed: 1/2 mineral interest
"""


def test_inventory_ocr_extract_and_runsheet_are_cited_and_versioned(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "deed.txt").write_text(_source_text(), encoding="utf-8")

    ctx = start_run(project)
    inventory = build_inventory(ctx)
    assert len(inventory) == 1
    assert inventory[0]["source_path"] == "deed.txt"

    ocr = run_ocr(ctx)
    assert ocr[0]["citation"] == "deed.txt#file"
    assert ocr[0]["method"] == "native_text"

    instruments = extract_and_reconcile(ctx, weak_threshold=0.60)
    assert instruments[0]["instrument_number"] == "2026-001234"
    assert "deed.txt#file" in instruments[0]["citation"]
    assert instruments[0]["status"] == "ACCEPTED"

    bundle = build_runsheet(ctx)
    assert len(bundle["runsheet"]) == 1
    assert (ctx.run_dir / "instruments.json").exists()
    assert (ctx.run_dir / "instruments.csv").exists()
    assert (project / OUTPUT_DIR_NAME / "latest_run.txt").read_text().strip() == ctx.run_id

    second = start_run(project)
    assert second.run_id != ctx.run_id
    assert ctx.run_dir.exists()


def test_preprocess_images_creates_copy_and_keeps_original(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "scan.png"
    image = Image.new("RGB", (500, 300), "white")
    ImageDraw.Draw(image).text((20, 20), "Instrument Number: 12345", fill="black")
    image.save(source)
    original = source.read_bytes()

    ctx = start_run(project)
    build_inventory(ctx)
    pages = preprocess_images(ctx)

    assert len(pages) == 1
    assert (ctx.run_dir / pages[0]["preprocessed_path"]).exists()
    assert source.read_bytes() == original


def test_tournament_quarantines_unsupported_candidate():
    cursor = [
        {
            "instrument_number": "",
            "grantor": "Ada Owner",
            "confidence": 0.9,
            "citation": "",
            "source_path": "scan.pdf",
            "source_locator": "page=1",
        }
    ]
    reconciled = tournament_reconcile(cursor, [], weak_threshold=0.4)
    assert reconciled[0]["status"] == "QUARANTINED - REVIEW REQUIRED"
    assert "missing instrument number" in reconciled[0]["reconciliation_notes"]
    assert "missing source citation" in reconciled[0]["reconciliation_notes"]


def test_export_preserves_template_and_escapes_formula_values(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "source.txt").write_text("Source evidence", encoding="utf-8")
    template = project / "template.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Original Template"
    sheet["A1"] = "DO NOT CHANGE"
    sheet["B2"] = "=SUM(1,2)"
    workbook.save(template)
    original_template = template.read_bytes()

    candidate = {
        "instrument_number": "2026-77",
        "instrument_type": "Oil and Gas Lease",
        "instrument_date": "01/02/2026",
        "recorded_date": "01/05/2026",
        "book": "10",
        "page": "20",
        "grantor": "=HYPERLINK(\"https://example.invalid\",\"Owner\")",
        "grantee": "Beacon LLC",
        "legal_description": "NE/4 Section 31",
        "interest_conveyed": "1/2",
        "lease_royalty_terms": "3/16",
        "confidence": 0.95,
        "citation": "source.txt#file",
        "source_path": "source.txt",
        "source_locator": "file",
    }
    cursor_json = project / "cursor.json"
    codex_json = project / "codex.json"
    cursor_json.write_text(json.dumps([candidate]), encoding="utf-8")
    codex_json.write_text(json.dumps([candidate]), encoding="utf-8")

    ctx = start_run(project)
    build_inventory(ctx)
    run_ocr(ctx)
    extract_and_reconcile(ctx, cursor_json=cursor_json, codex_json=codex_json)
    build_runsheet(ctx)
    exported = export_safe_xlsx(ctx, template, section="31-12N-24W")

    assert exported != template
    assert template.read_bytes() == original_template
    result = openpyxl.load_workbook(exported, data_only=False)
    assert result["Original Template"]["A1"].value == "DO NOT CHANGE"
    assert result["Original Template"]["B2"].value == "=SUM(1,2)"
    assert {
        "DBTF Runsheet",
        "DBTF Missing Docs",
        "DBTF OGL Draft",
        "DBTF Tract Drafts",
        "DBTF Run Manifest",
    }.issubset(result.sheetnames)
    headers = [cell.value for cell in result["DBTF Runsheet"][1]]
    grantor_column = headers.index("Grantor") + 1
    assert result["DBTF Runsheet"].cell(2, grantor_column).value.startswith("'=")
    result.close()
