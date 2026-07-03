"""DataBossX command-line entrypoint (stdlib argparse).

Subcommands:
  health                       run the baseline health check
  initdb [--db PATH]           create/verify the master SQLite DB
  ingest FILE                  load a CSV/XLSX notice list and print row count
  run-section --docs FILE ...  run the extract->reason pipeline for one section
                               and write a title-review report

`run-section` reads a JSON file: a list of {"source": "...", "text": "..."}.
It runs fully offline (deterministic) unless LLM provider keys are present.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import db, report  # noqa: E402
from tools.ingest import load_rows  # noqa: E402
from workflows.extraction_pipeline import run_pipeline  # noqa: E402


def _cmd_health(_args) -> int:
    import subprocess

    return subprocess.call([sys.executable, str(ROOT / "scripts" / "health_check.py")])


def _cmd_initdb(args) -> int:
    path = db.connect(Path(args.db) if args.db else None)
    print(f"[SUCCESS] DB ready at {path.execute('PRAGMA database_list').fetchone()[2]}")
    path.close()
    return 0


def _cmd_ingest(args) -> int:
    rows = load_rows(args.file)
    print(f"[OK] Loaded {len(rows)} rows from {args.file}")
    if rows:
        print(f"     Columns: {', '.join(rows[0].keys())}")
    return 0


def _cmd_run_section(args) -> int:
    payload = json.loads(Path(args.docs).read_text(encoding="utf-8"))
    documents = [(d["source"], d["text"]) for d in payload]

    conn = db.connect(Path(args.db) if args.db else None)
    try:
        # Re-run extraction locally too so the report can show the chain.
        from agents.extractor import ExtractorAgent

        extractor = ExtractorAgent()
        extracted = [extractor.run(text, source_url=src) for src, text in documents]
        decision = run_pipeline(documents, owner=args.owner, section=args.section, conn=conn)
    finally:
        conn.close()

    text = report.render_decision_report(args.owner, args.section, decision, extracted)
    out_dir = Path(args.out) if args.out else None
    path = report.write_report(text, args.section, out_dir=out_dir)

    print(f"[DECISION] {decision['status']} (confidence {decision['confidence']})")
    print(f"[REPORT]   {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="databossx", description="DataBossX title-research CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="run the baseline health check").set_defaults(func=_cmd_health)

    pi = sub.add_parser("initdb", help="create/verify the master DB")
    pi.add_argument("--db", default=None)
    pi.set_defaults(func=_cmd_initdb)

    pg = sub.add_parser("ingest", help="load a CSV/XLSX notice list")
    pg.add_argument("file")
    pg.set_defaults(func=_cmd_ingest)

    pr = sub.add_parser("run-section", help="run the pipeline for one section")
    pr.add_argument("--owner", required=True)
    pr.add_argument("--section", default="Sec 1")
    pr.add_argument("--docs", required=True, help="JSON: [{source, text}, ...]")
    pr.add_argument("--db", default=None)
    pr.add_argument("--out", default=None, help="output dir for the report")
    pr.set_defaults(func=_cmd_run_section)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
