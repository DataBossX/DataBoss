"""DataBossX self-builder package.

``build_registry`` scans the repo, merges curated workspace knowledge, and
emits the canonical registry files (MASTER_INVENTORY.jsonl,
CAPABILITY_REGISTRY.json, KNOWLEDGE_GRAPH.json, ...). See
``databossx/README.md``.
"""

from __future__ import annotations

__all__ = ["build_registry"]
__version__ = "1.0.0"
