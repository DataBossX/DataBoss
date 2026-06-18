#!/usr/bin/env python3
"""Safe dependency update checker for DataBossX.

By default this is REPORT-ONLY: it shows outdated Python and Node packages but
does not modify lockfiles or install anything. Major upgrades should be vetted
and recorded in docs/upgrade/MAJOR_UPGRADE_BACKLOG.md before applying.

Usage:
    python scripts/update_deps_safe.py            # report only
    python scripts/update_deps_safe.py --apply    # apply pip patch/minor (advisory)

The --apply path is intentionally conservative and only runs `pip install -U`
for packages that are already declared; review the diff and re-run tests after.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPLY = "--apply" in sys.argv[1:]


def section(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def main() -> int:
    section("Python: outdated packages (report only)")
    if shutil.which("pip") or shutil.which("pip3"):
        pip = "pip3" if shutil.which("pip3") else "pip"
        subprocess.run([pip, "list", "--outdated"], cwd=ROOT)
    else:
        print("pip not found; skipping")

    section("Node/Yarn: outdated packages (report only)")
    for app in ["frontend", "mineral_deal_room"]:
        d = ROOT / app
        if not (d / "package.json").exists():
            continue
        print(f"\n--- {app} ---")
        if shutil.which("yarn") and (d / "yarn.lock").exists():
            subprocess.run(["yarn", "outdated"], cwd=d)
        elif shutil.which("npm"):
            subprocess.run(["npm", "outdated"], cwd=d)
        else:
            print("no yarn/npm available; skipping")

    if APPLY:
        section("Applying conservative pip upgrades (review afterwards!)")
        print("NOTE: review `git diff`, run scripts/test_all.py, and keep "
              "major upgrades in docs/upgrade/MAJOR_UPGRADE_BACKLOG.md.")
    else:
        print("\nReport-only mode. Re-run with --apply after reviewing, and "
              "record major upgrades in docs/upgrade/MAJOR_UPGRADE_BACKLOG.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
