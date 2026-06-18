"""DataBossX Command Center — simple CLI menu + first-task orchestrator.

Run interactively:   python -m databossx.ui.command_center
Run the safety pass:  python -m databossx.ui.command_center --first-task
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..core import backup, diagnostics, health, paths, project_map, secret_scan
from ..excel import mock_workbook, review_workbook, workbook_fingerprint, workbook_inspector

MENU = """
=== DataBossX Command Center ===
 1. Health Check
 2. Backup Project
 3. Secret Scan
 4. Project Map
 5. Run Full Safety Runner (1-4)
 6. Create/Seed Registry DB         (roadmap)
 7. Create Mock Workbook
 8. Run Self-Test (first-task pass)
 9. Run Safe Autopilot Once         (roadmap)
10. Inspect Excel Workbook
11. Create Safe Review Workbook Copy
12. Export Workbook Links
13. Run TitlePreviewFixer 3-Row Preflight (roadmap/gated)
14. Show Next Ready Task
15. Build Diagnostics Bundle
16. Open Master Handoff Prompt
17. Exit
"""


def run_first_task() -> dict:
    """Execute the safety-first first-task sequence and return artifact paths."""
    ts = paths.timestamp()
    paths.ensure_dirs()
    artifacts: dict[str, str] = {}

    print("[1/10] Health check...")
    artifacts["health"] = str(health.run(ts))

    print("[2/10] Backup (excludes secrets)...")
    b = backup.create_backup(ts)
    artifacts["backup_zip"] = str(b.zip_path)
    artifacts["backup_manifest"] = str(b.manifest_path)
    artifacts["backup_log"] = str(b.log_path)

    print("[3/10] Secret scan...")
    artifacts["secret_scan"] = str(secret_scan.run(ts))

    print("[4/10] Project map...")
    artifacts["project_map"] = str(project_map.run(ts))

    print("[5/10] Create mock workbook...")
    mock = mock_workbook.create_mock_workbook(ts=ts)
    artifacts["mock_workbook"] = str(mock)

    print("[6/10] Fingerprint source (before)...")
    before = workbook_fingerprint.fingerprint(mock)

    print("[7/10] Inspect mock workbook + export links...")
    insp_report, links_csv, _ = workbook_inspector.run(mock, ts)
    artifacts["workbook_inspection"] = str(insp_report)
    artifacts["workbook_links"] = str(links_csv)

    print("[8/10] Create review copy (AI columns added to COPY only)...")
    review = review_workbook.create_review_copy(mock, ts)
    artifacts["review_copy"] = str(review)

    print("[9/10] Fingerprint source (after) + prove unchanged...")
    after = workbook_fingerprint.fingerprint(mock)
    proof = workbook_fingerprint.render_proof(before, after, ts)
    proof_path = paths.REPORTS / f"source_change_proof_{ts}.md"
    proof_path.write_text(proof)
    artifacts["source_change_proof"] = str(proof_path)
    if not workbook_fingerprint.unchanged(before, after):
        raise SystemExit("🚨 SAFETY FAILURE: source workbook hash changed!")

    print("[10/10] Diagnostics bundle...")
    d = diagnostics.build(ts)
    artifacts["diagnostics"] = str(d.zip_path)

    print("\n✅ First-task pass complete. Source workbook hash UNCHANGED.")
    for k, v in artifacts.items():
        print(f"   - {k}: {v}")
    return artifacts


def interactive() -> None:
    while True:
        print(MENU)
        choice = input("Select> ").strip()
        try:
            if choice == "1":
                print("->", health.run())
            elif choice == "2":
                r = backup.create_backup()
                print("->", r.zip_path, "sha256=", r.sha256[:16], "...")
            elif choice == "3":
                print("->", secret_scan.run())
            elif choice == "4":
                print("->", project_map.run())
            elif choice == "5":
                print("->", health.run())
                print("->", backup.create_backup().zip_path)
                print("->", secret_scan.run())
                print("->", project_map.run())
            elif choice == "7":
                print("->", mock_workbook.create_mock_workbook())
            elif choice == "8":
                run_first_task()
            elif choice == "10":
                p = input("Workbook path> ").strip()
                rep, csvp, _ = workbook_inspector.run(Path(p))
                print("->", rep, csvp)
            elif choice == "11":
                p = input("Source workbook path> ").strip()
                print("->", review_workbook.create_review_copy(Path(p)))
            elif choice == "12":
                p = input("Workbook path> ").strip()
                _, csvp, _ = workbook_inspector.run(Path(p))
                print("->", csvp)
            elif choice == "15":
                print("->", diagnostics.build().zip_path)
            elif choice == "14":
                print("Next ready task: run option 8 (self-test), then gated TitlePreviewFixer preflight.")
            elif choice in {"6", "9", "13", "16"}:
                print("Roadmap item — not yet implemented. See reports/ for status.")
            elif choice == "17":
                print("Bye.")
                return
            else:
                print("Unknown option.")
        except Exception as exc:  # noqa: BLE001 - surface errors to the operator
            print(f"ERROR: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DataBossX Command Center")
    parser.add_argument("--first-task", action="store_true", help="Run the safety-first first-task pass and exit")
    args = parser.parse_args(argv)
    if args.first_task:
        run_first_task()
        return 0
    if not sys.stdin.isatty():
        # Non-interactive context: default to the safe first-task pass.
        run_first_task()
        return 0
    interactive()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
