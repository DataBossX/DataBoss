"""Project registry -- the named land-title projects DataBossX operates on.

The mission names active projects (Horizon, Penterra, Roger Mills, Beckham
County, Ryder) and requires support for *future* projects. This module makes a
project a first-class, configurable thing rather than a path hard-coded in a
script: each project has a stable key, a display name, a default local root, and
a section label, and every root is overridable so the exact same code runs on
Rodney's Windows box and in a Linux test sandbox.

**No client data lives here.** Only project *names* and *default folder names*
are recorded -- never legal descriptions, owners, or drive-specific evidence.
The real source documents stay on the operator's machine under the configured
roots (this repo's public boundary forbids committing them).

Root resolution precedence (first hit wins):

1. an explicit ``root`` passed by the caller / CLI ``--root``,
2. ``DATABOSSX_<KEY>_ROOT``           (e.g. ``DATABOSSX_HORIZON_ROOT``),
3. ``DATABOSSX_ROOT`` / project subfolder under it,
4. the project's built-in Windows default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# The operator's primary working environment (mission spec). Used only to build
# *default* roots; never required to exist for imports or tests.
DEFAULT_BASE = r"D:\DataBoss\DataBossX_Final_Modular"


@dataclass(frozen=True)
class Project:
    """A registered land-title project."""

    key: str                 # stable slug, e.g. "horizon"
    name: str                # display name, e.g. "Horizon"
    section: str = ""        # canonical section label if the project has one
    folder: str = ""         # default subfolder name under the base working dir
    county: str = ""
    state: str = ""
    description: str = ""

    def default_root(self, base: Optional[str] = None) -> Path:
        base_path = Path(base or DEFAULT_BASE)
        return base_path / (self.folder or self.name)

    def resolve_root(self, override: Optional[str] = None,
                     base: Optional[str] = None) -> Path:
        """Resolve this project's source root (see module precedence)."""
        if override:
            return Path(override).expanduser()
        env_specific = os.environ.get(f"DATABOSSX_{self.key.upper()}_ROOT")
        if env_specific:
            return Path(env_specific).expanduser()
        env_base = os.environ.get("DATABOSSX_ROOT")
        if env_base:
            return Path(env_base).expanduser() / (self.folder or self.name)
        return self.default_root(base)


# The registered projects. Section labels are the publicly known survey labels
# for the work; they are not client-confidential data.
_PROJECTS: Dict[str, Project] = {
    p.key: p for p in [
        Project("horizon", "Horizon", section="31-12N-24W", folder="Horizon",
                county="Roger Mills", state="OK",
                description="Roger Mills cursory title report / OGL runsheet chain."),
        Project("penterra", "Penterra", folder="Penterra",
                description="Penterra land-title project."),
        Project("roger_mills", "Roger Mills", folder="RogerMills",
                county="Roger Mills", state="OK",
                description="Roger Mills County title report builder."),
        Project("beckham", "Beckham County", section="32", folder="Beckham",
                county="Beckham", state="OK",
                description="Beckham County Section 32 controlled-workbook project."),
        Project("ryder", "Ryder", folder="Ryder",
                description="Ryder land-title project."),
        # A clearly-synthetic golden project bundled in the repo so the whole
        # pipeline can be demonstrated end to end without any client data.
        Project("golden_demo", "Golden Demo (synthetic)", section="31-12N-24W",
                folder="", county="Synthetic", state="OK",
                description="Bundled synthetic project for demos, tests, and self-check."),
    ]
}

# Where the bundled golden project actually lives inside the repo.
GOLDEN_DEMO_KEY = "golden_demo"


def _repo_root() -> Path:
    # src/databossx/projects.py -> parents[2] is the repository root.
    return Path(__file__).resolve().parents[2]


def golden_demo_root() -> Path:
    """The in-repo synthetic project folder (created by ``databossx.demo``)."""
    return _repo_root() / "examples" / "projects" / "GOLDEN-DEMO"


def all_projects() -> List[Project]:
    return list(_PROJECTS.values())


def get_project(key_or_name: str) -> Optional[Project]:
    """Look a project up by key or (case-insensitive) display name."""
    if not key_or_name:
        return None
    k = str(key_or_name).strip().lower().replace(" ", "_").replace("-", "_")
    if k in _PROJECTS:
        return _PROJECTS[k]
    for p in _PROJECTS.values():
        if p.name.lower() == str(key_or_name).strip().lower():
            return p
    return None


def resolve_root(key_or_name: str, override: Optional[str] = None,
                 base: Optional[str] = None) -> Optional[Path]:
    """Resolve a project's source root, or ``None`` if the key is unknown.

    The golden demo always resolves to its in-repo folder unless explicitly
    overridden, so ``databossx demo`` works with zero configuration.
    """
    proj = get_project(key_or_name)
    if proj is None:
        return None
    if proj.key == GOLDEN_DEMO_KEY and not override \
            and not os.environ.get("DATABOSSX_GOLDEN_DEMO_ROOT"):
        return golden_demo_root()
    return proj.resolve_root(override=override, base=base)
