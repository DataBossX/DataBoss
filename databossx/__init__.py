"""DataBossX — local-first safety tooling for the title/runsheet workflow.

Operating law: **inspect → backup → edit → test → log → register. No silent edits.**

The public surface is intentionally small; import the submodules you need, e.g.::

    from databossx.core import secret_scan, backup
    from databossx.excel import workbook_inspector

A scriptable command-line interface is available as ``databossx`` (see
``databossx.cli``) or via ``python -m databossx``.
"""
from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
