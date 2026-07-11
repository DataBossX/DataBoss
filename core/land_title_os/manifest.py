"""One machine-readable manifest per land-section project (Move #10).

Every agent reads the same manifest instead of relying on giant prompts and
scattered memory. The manifest is plain JSON on disk so humans, agents, and
CI can all read and diff it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .util import utcnow_iso

REQUIRED_FIELDS = ("project_id", "client", "jurisdiction", "county", "section", "township", "range")


@dataclass
class ProjectManifest:
    project_id: str
    client: str
    jurisdiction: str
    county: str
    section: str
    township: str
    range: str
    source_locations: list = field(default_factory=list)
    templates: list = field(default_factory=list)
    deliverables: list = field(default_factory=list)
    required_checks: list = field(default_factory=list)
    open_issues: list = field(default_factory=list)
    approved_facts: list = field(default_factory=list)
    updated_at: str = field(default_factory=utcnow_iso)

    def validate(self) -> list[str]:
        """Return a list of problems; empty list means valid."""
        problems = []
        for name in REQUIRED_FIELDS:
            if not getattr(self, name, "").strip():
                problems.append(f"missing required field: {name}")
        for name in ("source_locations", "templates", "deliverables",
                     "required_checks", "open_issues", "approved_facts"):
            if not isinstance(getattr(self, name), list):
                problems.append(f"field must be a list: {name}")
        return problems

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        problems = self.validate()
        if problems:
            raise ValueError(f"refusing to save invalid manifest: {problems}")
        self.updated_at = utcnow_iso()
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "ProjectManifest":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = {f for f in cls.__dataclass_fields__}  # tolerate future extra keys
        m = cls(**{k: v for k, v in data.items() if k in known})
        problems = m.validate()
        if problems:
            raise ValueError(f"invalid manifest {path}: {problems}")
        return m


def find_manifests(root: str | Path) -> list[Path]:
    """All project manifests under a projects/ tree."""
    return sorted(Path(root).glob("*/manifest.json"))
