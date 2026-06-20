"""Enable ``python -m databossx`` as an alias for the ``databossx`` CLI."""
from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
