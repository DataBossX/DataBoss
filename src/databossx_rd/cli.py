"""CLI for isolated R&D probes. Not a production controller."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

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


def _fail_if(*verdicts: str) -> int:
    return 2 if any(verdict == "fail" for verdict in verdicts) else 0


def _write_observation(root: Path, writer_id: str, files: dict[str, dict]) -> None:
    target = root / "observations" / _stamp()
    with exclusive_writer(target, writer_id, [root]) as writer:
        written = None
        for name, payload in files.items():
            written = writer.write_json(name, payload)
        print(written)


def cmd_observe(args: argparse.Namespace) -> int:
    root = _output_root(args.output_root)
    ollama = probe_ollama()
    n8n = probe_n8n()
    _write_observation(
        root,
        "databossx-rd-observe",
        {
            "ollama.json": ollama,
            "n8n.json": n8n,
            "observation.json": {
                "schema_id": "databossx.rd.live_observation",
                "schema_version": "1.0",
                "repo_root": str(REPO_ROOT),
                "ollama": ollama,
                "n8n": n8n,
            },
        },
    )
    return _fail_if(ollama["verdict"], n8n["verdict"])


def cmd_probe_ollama(args: argparse.Namespace) -> int:
    result = probe_ollama()
    _write_observation(
        _output_root(args.output_root),
        "databossx-rd-ollama",
        {"ollama.json": result},
    )
    return _fail_if(result["verdict"])


def cmd_probe_n8n(args: argparse.Namespace) -> int:
    result = probe_n8n()
    _write_observation(
        _output_root(args.output_root),
        "databossx-rd-n8n",
        {"n8n.json": result},
    )
    return _fail_if(result["verdict"])


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
    return _fail_if(result["verdict"])


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


COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "observe": cmd_observe,
    "probe-ollama": cmd_probe_ollama,
    "probe-n8n": cmd_probe_n8n,
    "bench": cmd_bench,
}


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = COMMANDS.get(args.command)
    if handler is None:
        parser.error("unknown command")
    return handler(args)
