"""Architecture guard: enforce the layering the blueprint mandates.

`ingestion` and `validation` are read-only and must never import `repair`,
`source_verification`, or `orchestrator`. This keeps the validate path pure and
prevents accidental write-coupling.
"""
from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
FORBIDDEN = {"repair", "source_verification", "orchestrator", "reporting", "app", "cli"}
GUARDED_LAYERS = ("ingestion", "validation")


def _imports(py: Path) -> set[str]:
    tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
            # relative: from ..repair import x  -> module='repair' after leading dots stripped
            mods.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
    return mods


def test_pure_layers_do_not_import_repair() -> None:
    violations: list[str] = []
    for layer in GUARDED_LAYERS:
        for py in (PKG / layer).rglob("*.py"):
            for mod in _imports(py):
                base = mod.split(".")[-1]
                if base in FORBIDDEN or mod in FORBIDDEN:
                    violations.append(f"{py.relative_to(PKG)} imports {mod}")
    assert not violations, violations


def test_config_has_no_intra_package_deps() -> None:
    # config.py must be importable stand-alone (no cycles).
    mods = _imports(PKG / "config.py")
    assert not (mods & {"orchestrator", "validation", "repair", "ingestion"})
