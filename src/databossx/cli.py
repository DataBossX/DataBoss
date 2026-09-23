from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from databossx.governor.cycle import run_synthetic_cycle
from databossx.governor.inventory import write_census
from databossx.governor.policy_gate import scan_publication_policy
from databossx.governor.tournament import write_scorecard


def _git_head(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _write_docs_json(root: Path, filename: str, writer) -> int:
    dest = root / "docs" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    _print_json(writer(root, dest))
    return 0


def _cmd_census(root: Path, args: argparse.Namespace) -> int:
    return _write_docs_json(root, "INVENTORY_CENSUS.json", write_census)


def _cmd_policy_gate(root: Path, args: argparse.Namespace) -> int:
    result = scan_publication_policy(root)
    _print_json(result)
    return 1 if result["status"] == "FAIL" else 0


def _cmd_tournament(root: Path, args: argparse.Namespace) -> int:
    return _write_docs_json(root, "TOURNAMENT_SCORECARD.json", write_scorecard)


def _cmd_cycle(root: Path, args: argparse.Namespace) -> int:
    receipt = run_synthetic_cycle(root, base_commit=_git_head(root), worker_id=args.worker_id)
    print(
        json.dumps(
            {
                "receipt_id": receipt.receipt_id,
                "outcome": receipt.outcome,
                "envelope_hash": receipt.envelope_hash,
            },
            indent=2,
        )
    )
    return 0 if receipt.outcome.endswith("REVIEW") else 2


def _take_repo_root(argv: list[str]) -> tuple[list[str], str | None]:
    """Allow --repo-root before or after the subcommand without argparse conflicts."""
    cleaned: list[str] = []
    repo_root = None
    index = 0
    while index < len(argv):
        item = argv[index]
        if item == "--repo-root" and index + 1 < len(argv):
            repo_root = argv[index + 1]
            index += 2
            continue
        if item.startswith("--repo-root="):
            repo_root = item.split("=", 1)[1]
            index += 1
            continue
        cleaned.append(item)
        index += 1
    return cleaned, repo_root


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    cleaned, extracted_root = _take_repo_root(raw)
    parser = argparse.ArgumentParser(prog="databossx", description="DataBossX public-safe control CLI")
    parser.add_argument("--repo-root", default=".", help="repository root")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("census", help="count public-safe repository assets")
    sub.add_parser("policy-gate", help="scan the current tree for publication-policy defects")
    sub.add_parser("tournament", help="judge isolated _AI_* folders")
    cycle = sub.add_parser("cycle", help="run one synthetic L2 improvement cycle")
    cycle.add_argument("--worker-id", default="governor-l2")

    args = parser.parse_args(cleaned)
    root = Path(extracted_root if extracted_root is not None else args.repo_root).resolve()
    commands = {
        "census": _cmd_census,
        "policy-gate": _cmd_policy_gate,
        "tournament": _cmd_tournament,
        "cycle": _cmd_cycle,
    }
    handler = commands.get(args.command)
    if handler is None:
        raise SystemExit(2)
    return handler(root, args)
