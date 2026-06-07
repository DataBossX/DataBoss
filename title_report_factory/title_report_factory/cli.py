"""Command-line interface for the Title Report Factory.

    python -m title_report_factory run --config configs/section_27_diversified.json
    python -m title_report_factory inventory --config configs/section_27_diversified.json
    python -m title_report_factory doctor
"""
from __future__ import annotations

import json
import sys

try:
    import typer
    _HAVE_TYPER = True
except Exception:  # pragma: no cover
    _HAVE_TYPER = False

from .config_loader import load_config
from .utils import configure_logging


def _run(config: str, verbose: bool = False) -> int:
    configure_logging(verbose)
    from .pipeline import run_pipeline
    cfg = load_config(config)
    result = run_pipeline(cfg)
    print(json.dumps(result.model_dump(), indent=2, default=str))
    return 0


def _inventory(config: str, verbose: bool = False) -> int:
    configure_logging(verbose)
    from .file_inventory import inventory_files
    cfg = load_config(config)
    files = inventory_files(cfg.resolved_input_dirs())
    print(json.dumps([f.model_dump() for f in files], indent=2, default=str))
    return 0


def _doctor() -> int:
    configure_logging(False)
    from .ocr_engine import backends_available
    from .llm import llm_available
    from .okcounty_browser_downloader import downloader_ready
    ready, why = downloader_ready()
    report = {
        "ocr_backends": backends_available(),
        "llm_available": llm_available(),
        "downloader_ready": ready,
        "downloader_note": why,
    }
    print(json.dumps(report, indent=2))
    return 0


if _HAVE_TYPER:
    app = typer.Typer(add_completion=False, help="Automated cursory title report factory.")

    @app.command()
    def run(config: str = typer.Option(..., "--config", "-c"),
            verbose: bool = typer.Option(False, "--verbose", "-v")):
        """Run the full pipeline and print the JSON completion summary."""
        raise typer.Exit(_run(config, verbose))

    @app.command()
    def inventory(config: str = typer.Option(..., "--config", "-c"),
                  verbose: bool = typer.Option(False, "--verbose", "-v")):
        """Inventory local input files only."""
        raise typer.Exit(_inventory(config, verbose))

    @app.command()
    def doctor():
        """Report which optional backends (OCR, LLM, downloader) are available."""
        raise typer.Exit(_doctor())

    def main():
        app()
else:  # pragma: no cover - fallback when typer isn't installed
    def main():
        args = sys.argv[1:]
        if not args:
            print("usage: python -m title_report_factory {run|inventory|doctor} --config PATH")
            sys.exit(2)
        cmd = args[0]
        cfg = ""
        verbose = "--verbose" in args or "-v" in args
        if "--config" in args:
            cfg = args[args.index("--config") + 1]
        elif "-c" in args:
            cfg = args[args.index("-c") + 1]
        if cmd == "run":
            sys.exit(_run(cfg, verbose))
        if cmd == "inventory":
            sys.exit(_inventory(cfg, verbose))
        if cmd == "doctor":
            sys.exit(_doctor())
        print(f"unknown command: {cmd}")
        sys.exit(2)
