"""Ensure `src/` is importable when pytest is invoked from the repo root.

The repo-root CI (`.github/workflows/python-app.yml`) runs a bare `pytest`, whose
rootdir is the repository root — so the `pythonpath = ["src"]` in this package's
own pyproject.toml does not apply. This conftest, discovered along the collection
path, puts the package's src layout on sys.path regardless of invocation dir.
"""

import sys
from pathlib import Path

SRC = Path(__file__).parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
