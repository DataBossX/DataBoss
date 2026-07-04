"""Tiny module that records a launcher event (used by the Desktop launcher)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.settings import load_settings  # noqa: E402
from db.audit_logger import AuditLogger  # noqa: E402
from db.db_client import DatabaseManager  # noqa: E402


def main() -> int:
    settings = load_settings()
    db = DatabaseManager(settings.db_path)
    db.initialize_schema()
    AuditLogger(db).log_launcher_event("desktop_launch", "launched via desktop .bat")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
