"""Foundry configuration: root resolution, well-known directories, env overrides.

Resolution order for the DataBossX root:

1. ``DATABOSSX_ROOT`` environment variable (always wins — used by tests and CI).
2. The Windows-first default ``D:/Desktop/DataBossX`` when it exists.
3. The enclosing git/foundry checkout (walk up from cwd looking for a
   ``foundry/pyproject.toml`` or ``.git`` marker).
4. The current working directory as a last resort.

Discovery roots for ``databossx discover`` resolve similarly:
``DATABOSSX_DISCOVER_ROOTS`` (``os.pathsep``-separated) wins, otherwise the
Windows-first defaults ``D:/Desktop/Horizon`` and ``D:/Desktop/Penterra`` plus
``<root>/Horizon`` and ``<root>/Penterra`` for non-Windows checkouts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Tuple

ENV_ROOT = "DATABOSSX_ROOT"
ENV_DISCOVER_ROOTS = "DATABOSSX_DISCOVER_ROOTS"

WINDOWS_DEFAULT_ROOT = Path("D:/Desktop/DataBossX")
WINDOWS_DEFAULT_DISCOVER = (Path("D:/Desktop/Horizon"), Path("D:/Desktop/Penterra"))


def find_checkout_root(start: Path) -> Optional[Path]:
    """Walk up from ``start`` to the first directory that looks like a checkout."""
    cur = start.resolve()
    for candidate in (cur, *cur.parents):
        if (candidate / "foundry" / "pyproject.toml").is_file():
            return candidate
        if (candidate / ".git").exists():
            return candidate
    return None


@dataclass(frozen=True)
class FoundryConfig:
    """Immutable resolved configuration for one CLI invocation."""

    root: Path
    discover_roots: Tuple[Path, ...]

    @property
    def projects_dir(self) -> Path:
        return self.root / "projects"

    @property
    def plugins_dir(self) -> Path:
        return self.root / "plugins"

    @property
    def proposals_dir(self) -> Path:
        return self.root / "proposals"

    @property
    def state_dir(self) -> Path:
        """Foundry-owned state (versioned registry snapshots, trash)."""
        return self.root / "foundry_state"

    @property
    def trash_dir(self) -> Path:
        """Where anything that would otherwise be overwritten/deleted is moved."""
        return self.state_dir / "trash"


def load_config(
    cwd: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
) -> FoundryConfig:
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    env = os.environ if env is None else env

    root_override = env.get(ENV_ROOT, "").strip()
    if root_override:
        root = Path(root_override).expanduser()
    elif WINDOWS_DEFAULT_ROOT.is_dir():
        root = WINDOWS_DEFAULT_ROOT
    else:
        root = find_checkout_root(cwd) or cwd

    roots_override = env.get(ENV_DISCOVER_ROOTS, "").strip()
    if roots_override:
        discover_roots = tuple(
            Path(p).expanduser() for p in roots_override.split(os.pathsep) if p.strip()
        )
    else:
        candidates = list(WINDOWS_DEFAULT_DISCOVER)
        candidates.extend((root / "Horizon", root / "Penterra"))
        existing = tuple(p for p in candidates if p.is_dir())
        # If nothing exists yet, keep the Windows-first defaults so the
        # registry records what was looked for and where.
        discover_roots = existing or tuple(WINDOWS_DEFAULT_DISCOVER)

    return FoundryConfig(root=root, discover_roots=discover_roots)
