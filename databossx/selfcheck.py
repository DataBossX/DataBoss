"""Self-check ("doctor") -- confirm the system is healthy in plain language.

Runs a handful of fast checks and returns a clear PASS / WARN / FAIL for each,
plus an overall verdict. WARN means "works, but a feature is degraded" (e.g. a
missing optional dependency); FAIL means "core capability is broken". Nothing
here touches client data -- the only computation is an in-memory smoke test of
the exact-math core.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""
    fix: str = ""


@dataclass
class DoctorReport:
    checks: List[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.status != FAIL for c in self.checks)

    @property
    def verdict(self) -> str:
        if any(c.status == FAIL for c in self.checks):
            return FAIL
        if any(c.status == WARN for c in self.checks):
            return WARN
        return PASS

    def add(self, name, status, detail="", fix=""):
        self.checks.append(Check(name, status, detail, fix))


def _check_import(report: DoctorReport, module: str, purpose: str,
                  required: bool, fix: str) -> None:
    try:
        __import__(module)
        report.add(f"{module}", PASS, purpose)
    except Exception:
        report.add(f"{module}", FAIL if required else WARN,
                   f"missing -- {purpose}", fix)


def run_doctor() -> DoctorReport:
    report = DoctorReport()

    # Python version.
    v = sys.version_info
    if v >= (3, 9):
        report.add("Python", PASS, f"{v.major}.{v.minor}.{v.micro}")
    else:
        report.add("Python", FAIL, f"{v.major}.{v.minor} (need 3.9+)",
                   "Install Python 3.9 or newer.")

    # Core engine imports (required).
    _check_import(report, "pydantic", "report validation schema", True,
                  "py -m pip install pydantic")
    _check_import(report, "openpyxl", "Excel read/write", True,
                  "py -m pip install openpyxl")
    # Optional deliverable/feature deps.
    _check_import(report, "reportlab", "client PDF reports", False,
                  "py -m pip install reportlab")

    # Engine wiring.
    try:
        from horizon.interest import parse_interest  # noqa: F401
        from databossx.ownership import division_of_interest, MineralOwner
        report.add("engines", PASS, "horizon + databossx.ownership import OK")

        # In-memory smoke test of the exact-math core: a fully-leased unit must
        # distribute to exactly 8/8, or the math is broken.
        from fractions import Fraction
        owners = [MineralOwner("X", "1/2", royalty="1/8", lessee="Op"),
                  MineralOwner("Y", "1/2", royalty="1/8", lessee="Op")]
        out = division_of_interest(owners, "640")
        if out.total_nri == Fraction(1) and out.total_working_interest == Fraction(1) \
                and not out.defects:
            report.add("exact-math smoke test", PASS, "8/8 division balances exactly")
        else:
            report.add("exact-math smoke test", FAIL,
                       f"NRI={out.total_nri} WI={out.total_working_interest}",
                       "Ownership math regression -- do not use for release.")
    except Exception as exc:
        report.add("engines", FAIL, str(exc),
                   "Reinstall dependencies (see requirements.txt).")

    # Output writability (scratch under the repo).
    try:
        probe = Path(__file__).resolve().parent.parent / ".dbx_doctor_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        report.add("output writable", PASS, "working directory is writable")
    except OSError as exc:
        report.add("output writable", WARN, str(exc),
                   "Choose an output folder you have permission to write to.")

    return report


def format_report(report: DoctorReport) -> str:
    icon = {PASS: "[ OK ]", WARN: "[WARN]", FAIL: "[FAIL]"}
    lines = ["DataBossX self-check", "=" * 60]
    for c in report.checks:
        line = f"{icon.get(c.status, '[?]')}  {c.name:<22} {c.detail}"
        lines.append(line)
        if c.status != PASS and c.fix:
            lines.append(f"          fix: {c.fix}")
    lines.append("=" * 60)
    verdict_msg = {
        PASS: "All checks passed -- ready to run.",
        WARN: "Usable, but some optional features are degraded (see WARN above).",
        FAIL: "A core capability is broken -- resolve the FAIL items above.",
    }
    lines.append(f"Overall: {report.verdict} -- {verdict_msg[report.verdict]}")
    return "\n".join(lines)


if __name__ == "__main__":
    r = run_doctor()
    print(format_report(r))
    raise SystemExit(0 if r.ok else 1)
