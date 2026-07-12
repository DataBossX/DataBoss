from __future__ import annotations

import argparse
import json
from pathlib import Path

from databoss_orchestrator.adapters import FileDropAdapter
from databoss_orchestrator.models import AgentJob
from databoss_orchestrator.orchestrator import Orchestrator, initialize_control_plane


def build_adapters(root: Path, names: list[str]) -> dict[str, FileDropAdapter]:
    return {
        name: FileDropAdapter(name=name, inbox=root / "agents" / name / "inbox")
        for name in names
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DataBoss multi-AI control plane")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init")
    init_parser.add_argument("--root", required=True)

    health_parser = sub.add_parser("health")
    health_parser.add_argument("--root", required=True)
    health_parser.add_argument(
        "--agents",
        default="cursor,chatgpt,claude,gemini,codex,grok",
    )

    submit_parser = sub.add_parser("submit")
    submit_parser.add_argument("--root", required=True)
    submit_parser.add_argument("--job", required=True)
    submit_parser.add_argument(
        "--agents",
        default="cursor,chatgpt,claude,gemini,codex,grok",
    )

    args = parser.parse_args()
    root = Path(args.root)

    if args.command == "init":
        initialize_control_plane(root)
        print(f"Initialized: {root.resolve()}")
        return

    agent_names = [name.strip() for name in args.agents.split(",") if name.strip()]
    orchestrator = Orchestrator(root, build_adapters(root, agent_names))

    if args.command == "health":
        print(json.dumps(orchestrator.health_report(), indent=2))
        return

    job = AgentJob.model_validate_json(Path(args.job).read_text(encoding="utf-8"))
    receipt = orchestrator.submit(job)
    print(receipt.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
