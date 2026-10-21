"""Finding records and per-section machine-readable reports."""
from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

SEVERITIES = ("error", "warn", "info")


@dataclass
class Finding:
    section: str            # format|content|parity|pdf|letter|package
    check: str
    severity: str
    file: str
    message: str
    sheet: Optional[str] = None
    cell: Optional[str] = None
    expected: Optional[str] = None
    actual: Optional[str] = None


@dataclass
class Report:
    section: str
    tool_version: str = "1.0.0"
    findings: list[Finding] = field(default_factory=list)
    inputs: dict = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)

    def add(self, check: str, severity: str, file: str, message: str, **kw) -> None:
        assert severity in SEVERITIES
        self.findings.append(Finding(self.section, check, severity, os.path.basename(file), message, **kw))

    @property
    def errors(self) -> int:
        return sum(1 for f in self.findings if f.severity == "error")

    def to_dict(self) -> dict:
        by_check: dict[str, int] = {}
        for f in self.findings:
            by_check[f.check] = by_check.get(f.check, 0) + 1
        return {"section": self.section, "tool_version": self.tool_version,
                "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "inputs": self.inputs, "skipped": self.skipped,
                "summary": {"errors": self.errors, "warnings": sum(1 for f in self.findings if f.severity == "warn"),
                            "by_check": by_check},
                "findings": [asdict(f) for f in self.findings]}

    def write(self, out_dir: str) -> str:
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"report_{self.section}.json")
        with open(path, "w", encoding="utf8") as fh:
            json.dump(self.to_dict(), fh, indent=2, default=str)
        return path
