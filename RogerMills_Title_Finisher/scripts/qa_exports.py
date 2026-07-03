#!/usr/bin/env python3
"""QA consistency checks for the Section 31-12N-24W ownership exports.

Asserts the invariants a landman title report must never violate:
  1. Every tract foots: identified NMA + open/unreconciled NMA == gross acres.
  2. Every tract's decimal interests sum to exactly 1.000000.
  3. ownership_by_tract.csv and section_net_acre_summary.csv agree on the
     per-tract gross and on the section totals (identified / open / gross).
  4. The pull list and OGL register have their expected shape.

This is a regression guard: regenerate the exports (report/gen_exports.py) and
run this before committing. Exit code is non-zero if any check fails, so it can
gate CI. No network, no external deps — stdlib only. Invents nothing; it only
checks that the generated numbers are internally consistent.
"""
import csv
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXPORTS = os.path.normpath(os.path.join(HERE, "..", "exports"))

TOL_ACRE = 0.01      # acre foot-out tolerance
TOL_DEC = 1e-6       # decimal-interest tolerance
EXPECT_SECTION_GROSS = 637.42
EXPECT_PULL_ROWS = 63
EXPECT_OGL_ROWS = 69

failures = []


def check(cond, msg):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    if not cond:
        failures.append(msg)


def load(name):
    return list(csv.DictReader(open(os.path.join(EXPORTS, name), newline="")))


def is_open_row(row):
    note = (row.get("Note") or "").upper()
    return "OPEN" in note or "open" in row["Owner"].lower()


def main():
    own = load("ownership_by_tract.csv")
    summ = load("section_net_acre_summary.csv")

    gross, ident, openb, dec = {}, collections.defaultdict(float), \
        collections.defaultdict(float), collections.defaultdict(float)
    for r in own:
        t = r["Tract"]
        gross[t] = float(r["Tract gross ac"])
        nma = float(r["Net mineral acres"])
        dec[t] += float(r["Decimal interest in tract"])
        (openb if is_open_row(r) else ident)[t] += nma

    print("Per-tract foot-out and decimal-interest checks:")
    for t in sorted(gross, key=int):
        s = ident[t] + openb[t]
        check(abs(s - gross[t]) < TOL_ACRE,
              f"tract {t}: identified+open ({s:.2f}) == gross ({gross[t]:.2f})")
        check(abs(dec[t] - 1.0) < TOL_DEC,
              f"tract {t}: decimal interests sum to 1.0 (got {dec[t]:.6f})")

    ti = sum(ident.values())
    to = sum(openb.values())
    tg = sum(gross.values())
    print("\nSection totals:")
    check(abs(tg - EXPECT_SECTION_GROSS) < TOL_ACRE,
          f"section gross == {EXPECT_SECTION_GROSS} (got {tg:.2f})")
    check(abs(ti + to - tg) < TOL_ACRE,
          f"identified ({ti:.2f}) + open ({to:.2f}) == gross ({tg:.2f})")

    print("\nCross-export agreement (ownership_by_tract vs section summary):")
    srows = {r["Tract"]: r for r in summ if r["Tract"] != "TOTAL"}
    total_row = next((r for r in summ if r["Tract"] == "TOTAL"), None)
    check(total_row is not None, "summary has a TOTAL row")
    for t in sorted(gross, key=int):
        sr = srows.get(t)
        check(sr is not None, f"summary has tract {t}")
        if sr:
            check(abs(float(sr["Gross ac"]) - gross[t]) < TOL_ACRE,
                  f"tract {t}: summary gross == ownership gross ({gross[t]:.2f})")
            check(abs(float(sr["Identified NMA"]) - ident[t]) < TOL_ACRE,
                  f"tract {t}: summary identified ({sr['Identified NMA']}) "
                  f"== ownership identified ({ident[t]:.2f})")
            check(abs(float(sr["Open/unreconciled NMA"]) - openb[t]) < TOL_ACRE,
                  f"tract {t}: summary open ({sr['Open/unreconciled NMA']}) "
                  f"== ownership open ({openb[t]:.2f})")
    if total_row:
        check(abs(float(total_row["Identified NMA"]) - ti) < TOL_ACRE,
              f"summary TOTAL identified == {ti:.2f}")
        check(abs(float(total_row["Open/unreconciled NMA"]) - to) < TOL_ACRE,
              f"summary TOTAL open == {to:.2f}")

    print("\nPull list and OGL register shape:")
    pull = load("open_items_pull_list.csv")
    check(len(pull) == EXPECT_PULL_ROWS,
          f"pull list has {EXPECT_PULL_ROWS} rows (got {len(pull)})")
    cats = collections.Counter(r["Category"] for r in pull)
    check(sum(cats.values()) == len(pull),
          "every pull-list row has a Category")
    print("    pull-list categories: " +
          ", ".join(f"{v} {k}" for k, v in cats.most_common()))
    ogl = load("ogl_register.csv")
    check(len(ogl) == EXPECT_OGL_ROWS,
          f"OGL register has {EXPECT_OGL_ROWS} rows (got {len(ogl)})")

    print()
    if failures:
        print(f"QA FAILED: {len(failures)} check(s) failed.")
        return 1
    print("QA PASSED: all export-consistency checks green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
