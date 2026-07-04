"""Execute an APPROVED quarantine plan safely. Never deletes.

Reads output/quarantine_plan.csv. Only acts on rows where an `approved` column
equals YES/TRUE/1 (Rodney adds this column in Excel). Everything else is a
dry-run preview. Moves (never copies-then-deletes destructively, never removes)
duplicates into <root>/quarantine/duplicates/<relpath>, verifies the file's
sha256 is unchanged after the move, and records every action in
quarantine_manifest.csv so it is fully reversible.

Safety:
- Refuses protected roots (Horizon / Penterra).
- Refuses to overwrite an existing destination.
- Default is DRY-RUN; pass --apply to actually move.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import List

from report_pipeline import common as C

PROTECTED = ("horizon", "penterra")


def _is_protected(path: Path) -> bool:
    return any(seg.lower() in PROTECTED for seg in Path(path).parts)


def _approved(row: dict) -> bool:
    return str(row.get("approved", "")).strip().lower() in ("yes", "true", "1", "y")


def run(root: Path, out: Path, apply: bool, log) -> List[dict]:
    plan = C.read_csv(out / "quarantine_plan.csv")
    manifest: List[dict] = []
    if not plan:
        log.info("quarantine: no plan rows (nothing to do).")
        return manifest

    has_approved_col = any("approved" in r for r in plan)
    if not has_approved_col:
        log.warning("quarantine: plan has no 'approved' column — add approved=YES to rows "
                    "in quarantine_plan.csv to authorize moves. Running DRY-RUN only.")

    for row in plan:
        src = Path(row["path"])
        if not _approved(row):
            log.info("SKIP (not approved): %s", row.get("relpath", src))
            continue
        if _is_protected(src):
            log.error("REFUSE (protected root): %s", src)
            continue
        if not src.exists():
            log.warning("SKIP (missing source): %s", src)
            continue

        dest = root / "quarantine" / "duplicates" / row.get("relpath", src.name)
        if dest.exists():
            log.error("REFUSE (dest exists, no overwrite): %s", dest)
            continue

        entry = {
            "src": str(src), "dest": str(dest),
            "sha256": row.get("sha256", ""), "action": "MOVE",
            "applied": "no", "generated_at": C.now_iso(),
        }
        if not apply:
            log.info("DRY-RUN would move: %s -> %s", src, dest)
        else:
            before = C.sha256_file(src)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            after = C.sha256_file(dest)
            if before != after:
                log.error("INTEGRITY ERROR after move (hash changed): %s", dest)
                entry["action"] = "MOVE_HASH_MISMATCH"
            entry["applied"] = "yes"
            log.info("MOVED: %s -> %s", src, dest)
        manifest.append(entry)

    if manifest:
        C.write_table(out, "quarantine_manifest",
                      ["src", "dest", "sha256", "action", "applied", "generated_at"], manifest)
    log.info("quarantine: %d rows in manifest (apply=%s)", len(manifest), apply)
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="quarantine-exec", description="Execute an approved quarantine plan (safe)")
    ap.add_argument("--root", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--apply", action="store_true", help="actually move files (default: dry-run)")
    args = ap.parse_args(argv)
    root = C.resolve_root(args.root)
    out = C.output_dir(root, args.out)
    log = C.get_logger("quarantine", out=out)
    run(root, out, args.apply, log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
