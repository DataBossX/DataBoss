"""DataBossX trusted-kernel package.

This package implements the local-first, modular-monolith kernel described in
``docs/DATABOSSX_OS_BLUEPRINT.md``: an evidence-grounded domain model, a
content-addressed vault, a numbered SQL migration runner, a durable task
graph with leases, an append-only audit log, and a thin FastAPI control API.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
