"""Command line entry point.

Subcommands:

``selftest``  prove the kernel's invariants offline. Exit 0 only if all pass.
``canary``    the fast offline subset, no network of any kind.
``audit``     the Gate 0 read-only audit for this host.

Every subcommand writes only into its own append-only run directory. None of
them claims the queue, mutates a workbook, or removes the HOLD. Claiming is a
separate, deliberate step and is not reachable from this CLI by accident.
"""

import argparse
import os
import sys
import time

from .audit import run_audit
from .constants import HOLD
from .safety import canonical_json_bytes, sha256_hex
from .tower import offline_canary, selftest


def _run_dir(base, kind):
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = os.path.join(base, "{0}_{1}".format(kind, stamp))
    os.makedirs(path, exist_ok=True)
    return path


def _emit(report, run_dir, name):
    """Write the report and its digest side by side, append-only."""
    payload = canonical_json_bytes(report)
    digest = sha256_hex(payload)
    out_path = os.path.join(run_dir, name)
    with open(out_path, "xb") as handle:
        handle.write(payload)
    with open(out_path + ".sha256", "x", encoding="utf-8") as handle:
        handle.write("{0}  {1}\n".format(digest, name))
    return out_path, digest


def _print_checks(report):
    for check in report["checks"]:
        marker = "PASS" if check["passed"] else "FAIL"
        print("  [{0}] {1} -- {2}".format(marker, check["name"], check["detail"]))
    print(
        "{0}: {1}/{2} passed, {3} failed".format(
            report["suite"], report["passed"], report["total"], report["failed"]
        )
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="run_control_tower")
    parser.add_argument(
        "command", choices=("selftest", "canary", "audit"), help="what to run"
    )
    parser.add_argument(
        "--run-root",
        default=os.environ.get("DBX_CONTROL_TOWER_RUNS", "control_tower_runs"),
        help="local append-only directory for run output",
    )
    parser.add_argument("--v12-path", default=os.environ.get("DBX_V12_PATH"))
    parser.add_argument("--repo-path", default=os.environ.get("DBX_REPO_PATH", "."))
    parser.add_argument("--workbook-dir", default=os.environ.get("DBX_WORKBOOK_DIR"))
    args = parser.parse_args(argv)

    started = time.time()
    run_dir = _run_dir(args.run_root, args.command)

    if args.command in ("selftest", "canary"):
        report = selftest() if args.command == "selftest" else offline_canary()
        report["started_at_epoch"] = started
        report["ended_at_epoch"] = time.time()
        _print_checks(report)
        path, digest = _emit(report, run_dir, "{0}_report.json".format(args.command))
        print("report: {0}".format(path))
        print("sha256: {0}".format(digest))
        print("hold:   {0}".format(HOLD))
        return 0 if report["ok"] else 1

    # audit -- read-only, and it refuses to run on an unproven build.
    pre = selftest()
    if not pre["ok"]:
        print("selftest FAILED {0}/{1}; refusing to audit".format(pre["failed"], pre["total"]))
        _print_checks(pre)
        return 1

    report = run_audit(
        client=None,
        v12_path=args.v12_path,
        repo_path=args.repo_path,
        workbook_dir=args.workbook_dir,
    )
    report["selftest_passed"] = pre["passed"]
    report["selftest_total"] = pre["total"]
    report["started_at_epoch"] = started
    report["ended_at_epoch"] = time.time()
    report["hold"] = HOLD
    path, digest = _emit(report, run_dir, "S32_GATE0_LOCAL_AUDIT.json")

    print("audit completeness: {0}".format(report["audit_completeness"]))
    print("v12 ruling:         {0}".format(report["v12_ruling"]))
    if report["unreachable_items"]:
        print("unreachable:        {0}".format(", ".join(report["unreachable_items"])))
    print("workbook opened:    {0}".format(report["workbook_opened"]))
    print("report: {0}".format(path))
    print("sha256: {0}".format(digest))
    print("hold:   {0}".format(HOLD))

    # An audit that could not see its target is not a pass.
    return 0 if report["audit_completeness"] == "COMPLETE" else 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
