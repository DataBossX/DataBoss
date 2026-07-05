"""Section 31-12N-24W Roger Mills ownership/title automation app.

The workbook is the product; this package is the machine that keeps improving
it. Public entry points:

    from section31_app.config import Section31Config
    from section31_app.pipeline import run_pipeline
    from section31_app.bootstrap import bootstrap
"""

from __future__ import annotations

from .config import Section31Config
from .pipeline import run_pipeline

__all__ = ["Section31Config", "run_pipeline", "__version__"]
__version__ = "1.0.0"
