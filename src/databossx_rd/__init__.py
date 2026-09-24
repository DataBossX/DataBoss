"""Isolated, reversible DataBossX R&D probes and bench scaffolding.

This package is not an orchestrator, agent controller, or production parser.
It has no write authority outside an explicit isolated root (default:
``runtime/rd``). Production packages must not import it.
"""

from .constants import UNKNOWN
from .n8n_guard import probe_n8n
from .ollama_inventory import probe_ollama
from .parser_bench import load_bench_spec, run_parser_bench, validate_bench_spec

__all__ = [
    "UNKNOWN",
    "load_bench_spec",
    "probe_n8n",
    "probe_ollama",
    "run_parser_bench",
    "validate_bench_spec",
]

__version__ = "0.1.0-rd"
