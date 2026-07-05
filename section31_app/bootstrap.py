"""Create the Roger Mills folder structure and seed a template workbook.

Idempotent: safe to run on every launch. Creates the managed subfolders, drops
a short README in each so an operator knows what belongs where, and seeds an
empty-but-valid final workbook if one doesn't exist yet -- so the product is
always present, even before the first real run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from .config import FINAL_WORKBOOK_NAME, Section31Config
from .exporter import seed_template
from .logbook import LogBook

_FOLDER_READMES = {
    "app": "Section 31 automation app code lives here (or is launched from here).",
    "candidates": "Drop candidate XLSX workbooks / runsheets to be scanned here.",
    "images": "Source images: recorded document PDFs/TIFFs pulled for the report.",
    "archive": "Non-final files moved out of the main folder after each export.",
    "qa": "QA logs and check results from each run.",
    "logs": "Run logs and the audit trail (secret-scrubbed).",
    "exports": "Timestamped copies of every exported final workbook.",
}


def bootstrap(cfg: Section31Config, log: LogBook | None = None) -> Dict:
    log = log or LogBook(cfg.logs_dir / "section31_audit.log")
    cfg.ensure_workspace()
    log.info(f"workspace ready at {cfg.root}")

    key_to_dir = {
        "app": cfg.app_dir, "candidates": cfg.candidates_dir,
        "images": cfg.images_dir, "archive": cfg.archive_dir,
        "qa": cfg.qa_dir, "logs": cfg.logs_dir, "exports": cfg.exports_dir,
    }
    for key, folder in key_to_dir.items():
        readme = folder / "_README.txt"
        if not readme.exists():
            try:
                readme.write_text(_FOLDER_READMES[key] + "\n", encoding="utf-8")
            except OSError:
                pass

    seeded = False
    if not cfg.final_workbook.exists():
        try:
            seed_template(cfg.final_workbook)
            seeded = True
            log.info(f"seeded template workbook: {FINAL_WORKBOOK_NAME}")
        except Exception as exc:
            log.warn(f"could not seed template: {type(exc).__name__}")

    return {"root": str(cfg.root), "seeded_template": seeded,
            "subfolders": [str(d) for d in cfg.managed_dirs]}
