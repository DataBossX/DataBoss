"""CLI for isolated R&D probes. Not a production controller."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .constants import DEFAULT_RUNTIME_RD, REPO_ROOT
from .n8n_guard import probe_n8n
from .ollama_inventory import probe_ollama
from .parser_bench import load_bench_spec, run_parser_bench
from .writer import exclusive_writer


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _output_root(explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit)
    return DEFAULT_RUNTIME_RD


def cmd_observe(args: argparse.Namespace) -> int:
    root = _output_root(args.output_root)
    target = root / "observations" / _stamp()
    ollama = probe_ollama()
    n8n = probe_n8n()
    combined = {
        "schema_id": "databossx.rd.live_observation",
        "schema_version": "1.0",
        "repo_root": str(REPO_ROOT),
        "ollama": ollama,
        "n8n": n8n,
    }
    with exclusive_writer(target, "databossx-rd-observe", [root]) as writer:
        writer.write_json("ollama.json", ollama)
        writer.write_json("n8n.json", n8n)
        writer.write_json("observation.json", combined)
        print(writer.target / "observation.json")
    if ollama["verdict"] == "fail" or n8n["verdict"] == "fail":
        return 2
    return 0


def cmd_probe_ollama(args: argparse.Namespace) -> int:
    result = probe_ollama()
    root = _output_root(args.output_root)
    target = root / "observations" / _stamp()
    with exclusive_writer(target, "databossx-rd-ollama", [root]) as writer:
        writer.write_json("ollama.json", result)
        print(writer.target / "ollama.json")
    return 0 if result["verdict"] != "fail" else 2


def cmd_probe_n8n(args: argparse.Namespace) -> int:
    result = probe_n8n()
    root = _output_root(args.output_root)
    target = root / "observations" / _stamp()
    with exclusive_writer(target, "databossx-rd-n8n", [root]) as writer:
        writer.write_json("n8n.json", result)
        print(writer.target / "n8n.json")
    return 0 if result["verdict"] != "fail" else 2


def cmd_bench(args: argparse.Namespace) -> int:
    spec = load_bench_spec()
    root = _output_root(args.output_root)
    result = run_parser_bench(
        spec=spec,
        output_root=root / "bench" / _stamp(),
        allowed_roots=[root],
        mode=args.mode,
    )
    print(result.get("output_path"))
    return 0 if result["verdict"] != "fail" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m databossx_rd",
        description="Read-only DataBossX R&D probes and parser-bench scaffolding.",
    )
    parser.add_argument(
        "--output-root",
        help="Isolated output root (default: runtime/rd). Production paths are rejected.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("observe", help="Probe loopback Ollama and n8n; write isolated evidence.")
    sub.add_parser("probe-ollama", help="Read-only Ollama inventory.")
    sub.add_parser("probe-n8n", help="Read-only n8n version/safety guard.")
    bench = sub.add_parser("bench", help="Validate or run the isolated parser bench.")
    bench.add_argument(
        "--mode",
        choices=("spec_only", "current_only"),
        default="spec_only",
        help="spec_only never extracts. current_only uses the in-repo parser only.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "observe":
        return cmd_observe(args)
    if args.command == "probe-ollama":
        return cmd_probe_ollama(args)
    if args.command == "probe-n8n":
        return cmd_probe_n8n(args)
    if args.command == "bench":
        return cmd_bench(args)
    parser.error("unknown command")
    return 2
