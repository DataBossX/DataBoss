"""Legal-authority enrichment (research aid, NOT legal advice).

Maps curative / chain-defect categories to verified Oklahoma authorities
retrieved via the Legal Data Hunter MCP (CourtListener / Caselaw Access
Project). Every citation carries a URL the user can open and verify; non-OK
results were excluded at curation time. Nothing here is a title opinion.

Refresh: the dataset can be regenerated with the Legal Data Hunter MCP, but the
app itself ships the static JSON so it runs offline on the user's machine.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).with_name("authorities.json")

# curative 'category' -> authorities key
_ALIASES = {
    "wild-deed": "wild-deed",
    "probate": "probate",
    "entity-succession": "entity-succession",
    "ogl": "ogl-hbp",
    "lease": "ogl-hbp",
}


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads(_DATA.read_text())


def disclaimer() -> str:
    return _load()["_meta"]["disclaimer"]


def for_category(category: str) -> list[dict]:
    data = _load()
    key = _ALIASES.get(category, category)
    return data.get(key, [])


def citation_line(a: dict) -> str:
    label = a.get("cite") or a.get("statute") or a.get("note") or ""
    url = a.get("url")
    return f"{label}" + (f" <{url}>" if url else "")


def authorities_for(category: str) -> str:
    items = for_category(category)
    if not items:
        return ""
    return " | ".join(citation_line(a) for a in items)
