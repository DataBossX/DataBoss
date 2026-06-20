"""Load every specs/*.agent.yaml into a validated, name-keyed registry."""

from __future__ import annotations

from pathlib import Path

from evoswarm.agents.base import Agent

SPECS_DIR = Path(__file__).resolve().parents[3] / "specs"


def load_registry(specs_dir: Path = SPECS_DIR) -> dict[str, Agent]:
    registry: dict[str, Agent] = {}
    for path in sorted(specs_dir.glob("*.agent.yaml")):
        agent = Agent.from_yaml(path)
        registry[agent.spec.name] = agent
    return registry


if __name__ == "__main__":  # quick self-test: `python -m evoswarm.agents.registry`
    reg = load_registry()
    for name, agent in reg.items():
        print(f"{name:18s} {agent.spec.role.value:16s} model={agent.spec.model}")
    print(f"\n{len(reg)} agents validated OK")
