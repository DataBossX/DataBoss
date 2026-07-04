"""Headless CLI entrypoint: run the validation agent against a workbook.

Usage:
    python -m core.cli /path/to/workbook.xlsx
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import load_settings  # noqa: E402
from db.audit_logger import AuditLogger  # noqa: E402
from db.db_client import DatabaseManager  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m core.cli <workbook.xlsx>", file=sys.stderr)
        return 2
    workbook = Path(argv[1])
    if not workbook.exists():
        print(f"workbook not found: {workbook}", file=sys.stderr)
        return 2

    settings = load_settings()
    db = DatabaseManager(settings.db_path)
    db.initialize_schema()
    audit = AuditLogger(db)

    from core.orchestrator import Orchestrator

    result = Orchestrator(settings, db, audit).run(workbook)
    print(f"Run:        {result.run_id}")
    print(f"Folder:     {result.run_folder}")
    print(f"Final state:{result.final_state.value}")
    print(f"Certified:  {result.certified}")
    print(f"Iterations: {result.iterations}")
    print(f"Escalations:{len(result.escalations)}")
    print(f"Exports:    {len(result.export_files)} (zip: {result.export_zip})")
    db.close()
    return 0 if result.certified else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
