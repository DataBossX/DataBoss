#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_sample_data.py -- generate a SYNTHETIC, clearly-labeled title-document
corpus for exercising the Grocery Report pipeline.

The documents are FICTIONAL test fixtures. They contain no real ownership,
lease, party, or recording data. Use them only to validate the machinery.

Usage:
    py make_sample_data.py --dest .\\_synthetic_corpus
    py grocery_report_pipeline.py --root .\\_synthetic_corpus
"""
from __future__ import annotations

import argparse
from pathlib import Path

from grocery_report_pipeline import make_synthetic_corpus


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dest", default="./_synthetic_corpus",
                    help="Folder to write synthetic documents into.")
    args = ap.parse_args()
    dest = Path(args.dest)
    make_synthetic_corpus(dest)
    files = sorted(p.name for p in dest.glob("*"))
    print(f"Wrote {len(files)} SYNTHETIC documents to {dest}:")
    for f in files:
        print(f"  - {f}")
    print("\nThese are fictional test fixtures -- not real title data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
