from __future__ import annotations

import argparse
import json
import sys

from . import pipeline
from .config import ConfigError, load_config


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aqa", description="Abstract reconciliation and QA (read-only on sources)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run all stages into a fresh run directory")
    r.add_argument("--config", required=True)
    r.add_argument("--run-id")
    r.add_argument("--resume", metavar="RUN_ID", help="resume an existing run (completed stages with unchanged inputs are reused)")
    v = sub.add_parser("verify", help="re-hash the artifacts named in a qa_receipt.json")
    v.add_argument("final_dir")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "verify":
            bad = pipeline.verify_receipt(a.final_dir)
            print(json.dumps({"ok": not bad, "problems": bad}, indent=2))
            return 0 if not bad else 2
        cfg = load_config(a.config)
        res = pipeline.execute(cfg, run_id=a.resume or a.run_id, resume=bool(a.resume))
    except (ConfigError, FileExistsError, FileNotFoundError, PermissionError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    out = {k: v for k, v in res.items() if k not in ("sections", "findings")}
    if res.get("findings"):
        out["findings"] = res["findings"]
    print(json.dumps(out, indent=2, default=str))
    return 0 if res["status"].startswith("AUTOMATED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
