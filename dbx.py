#!/usr/bin/env python3
"""DataBossX Command Center -- root entry point.

The ``databossx`` package ships under ``src/`` (src layout). This tiny shim puts
``src`` on the import path and hands off to the CLI, so a non-programmer can run
the tool with a plain, copy-pasteable command from the repo root:

    python dbx.py doctor
    python dbx.py demo
    python dbx.py run --project horizon --root /path/to/files
    python dbx.py calc --wi 1 --royalty 1/8

(Equivalent to ``PYTHONPATH=src python -m databossx ...``.)
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from databossx.cli import main  # noqa: E402  (after sys.path setup)

if __name__ == "__main__":
    raise SystemExit(main())
