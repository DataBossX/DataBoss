"""Export the required side-car artifacts and the final JSON completion summary.

Outputs (all under the run's outputs folder):
  * Finished Excel workbook            (written by excel_template_writer)
  * Full text index sheet             (in the workbook + index_text.json)
  * OCR text cache                    (ocr_cache/*.txt)
  * Source document inventory         (source_inventory.json)
  * Confidence summary JSON           (confidence_summary.json)
  * Missing document & curative report(curative_issues.json)
  * Final completion summary          (completion_summary.json)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .models import Document, PipelineResult, SourceFile
from .utils import LOG, safe_filename


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def export_ocr_cache(docs: List[Document], out_dir: Path) -> int:
    cache = out_dir / "ocr_cache"
    cache.mkdir(parents=True, exist_ok=True)
    n = 0
    for d in docs:
        if not d.text:
            continue
        fname = safe_filename(f"{d.doc_id}_{Path(d.source_file).stem}") + ".txt"
        (cache / fname).write_text(d.text, encoding="utf-8")
        n += 1
    return n


def export_source_inventory(files: List[SourceFile], out_dir: Path) -> None:
    write_json(out_dir / "source_inventory.json",
               [f.model_dump() for f in files])


def export_index_json(index_rows: List[dict], out_dir: Path) -> None:
    write_json(out_dir / "index_text.json", index_rows)


def export_confidence_summary(qc: dict, out_dir: Path) -> None:
    write_json(out_dir / "confidence_summary.json", qc)


def export_curative(issues: List[dict], missing: List[str], out_dir: Path) -> None:
    write_json(out_dir / "curative_issues.json",
               {"curative_issues": issues, "missing_documents": missing})


def export_completion_summary(result: PipelineResult, out_dir: Path) -> Path:
    path = out_dir / "completion_summary.json"
    write_json(path, result.model_dump())
    LOG.info("Completion summary written: %s", path)
    return path
