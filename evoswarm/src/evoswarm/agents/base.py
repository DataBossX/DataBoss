"""Base agent: loads a strict AgentSpec from YAML and exposes a typed run()."""

from __future__ import annotations

from pathlib import Path

import yaml

from evoswarm.schemas import AgentSpec, SwarmState


class Agent:
    def __init__(self, spec: AgentSpec):
        self.spec = spec

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Agent":
        data = yaml.safe_load(Path(path).read_text())
        # Config boundary: YAML has no native Decimal/enum, so we allow JSON-style
        # coercion here (strict=False) while every *in-process* construction stays
        # strict. The model still fully validates ranges, patterns and enum membership.
        return cls(AgentSpec.model_validate(data, strict=False))

    def run(self, state: SwarmState) -> SwarmState:
        """Default no-op node. Subclasses / LLM-backed agents override this.

        Kept pure (returns a new-ish state) so nodes are easy to unit-test and
        the EvoLoop can replay them deterministically against eval fixtures.
        """
        state.history.append(f"{self.spec.name} ({self.spec.role.value}) visited")
        return state
