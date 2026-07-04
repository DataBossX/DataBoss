"""The Autonomous Improvement Loop -- the "Perfect" path.

Mission section 3. The orchestrator runs, at most ``max_loops`` (default 5)
times:

  Ingest  -> load the current (latest) version of the report
  Validate-> run gates against the Golden Source requirements
  Repair  -> if a structural defect is found, repair via lxml XML editing
  Evaluate-> if validation passes, emit a NEW version into rogermillsfinalreports
  Iterate -> otherwise record the failure type in the audit log and retry

The loop is *convergent and bounded*: it stops on the first pass, on exhaustion
(``max_loops``), or when a pass makes no repair progress (to avoid spinning).
Every iteration writes a new ``_vNNN`` file -- nothing is overwritten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .audit import AuditLog
from .config import HorizonConfig
from .models import ReportModel
from .repair import repair_workbook
from .validation import Requirements, ValidationReport, load_requirements, validate_report
from .versioning import latest_version, next_version_path


@dataclass
class LoopIteration:
    index: int
    version_in: Optional[str]
    version_out: Optional[str]
    passed: bool
    validation_summary: str
    repaired: bool
    repair_fixes: List[str] = field(default_factory=list)


@dataclass
class OrchestrationResult:
    iterations: List[LoopIteration] = field(default_factory=list)
    final_version: Optional[Path] = None
    converged: bool = False
    exhausted: bool = False

    @property
    def loops_run(self) -> int:
        return len(self.iterations)


class Orchestrator:
    """Drives the bounded improvement loop over a single report base name."""

    def __init__(self, cfg: HorizonConfig, audit: AuditLog) -> None:
        self.cfg = cfg
        self.audit = audit

    # -- individual stages --------------------------------------------------
    def ingest(self, base_stem: str) -> Optional[Path]:
        """Return the latest version to work from (mission: Ingest)."""
        current = latest_version(self.cfg.final_reports, base_stem)
        self.audit.info("ingest", f"current={current.name if current else '(none)'}")
        return current

    def validate(self, report: ReportModel, requirements: Requirements) -> ValidationReport:
        vr = validate_report(report, requirements)
        self.audit.info("validate", f"passed={vr.passed} issues[{vr.summary()}]")
        return vr

    def repair(self, src: Path, base_stem: str) -> Optional[Path]:
        """Repair a defective workbook into a new version. Returns the new path
        if a repair was actually made, else None."""
        candidate = next_version_path(self.cfg.final_reports, base_stem)
        result = repair_workbook(src, candidate)
        if result.error:
            self.audit.error("repair_failed", result.error)
            if candidate.exists():
                candidate.unlink()
            return None
        if result.repaired:
            self.audit.info(
                "repair",
                f"{src.name} -> {candidate.name} fixes={len(result.fixes)} "
                f"media_preserved={result.media_preserved}",
            )
            return candidate
        # No structural fixes needed; discard the throwaway copy.
        if candidate.exists():
            candidate.unlink()
        return None

    def emit_version(self, report: ReportModel, base_stem: str, src: Optional[Path]) -> Path:
        """Evaluate step: persist a passing report as a new version."""
        from .report_io import write_report

        out = next_version_path(self.cfg.final_reports, base_stem)
        # Preserve any embedded plats/media from the ingested version.
        write_report(report, out, template=src)
        self.audit.info("emit_version", f"wrote {out.name}")
        return out

    # -- the loop -----------------------------------------------------------
    def run(self, report: ReportModel, base_stem: str,
            requirements: Optional[Requirements] = None) -> OrchestrationResult:
        """Run the bounded Ingest->Validate->Repair->Evaluate->Iterate loop."""
        self.cfg.final_reports.mkdir(parents=True, exist_ok=True)
        reqs = requirements or load_requirements(
            self.cfg.root / self.cfg.golden_source_name
        )
        self.audit.info("loop_start", f"base={base_stem} requirements={reqs.source}")

        result = OrchestrationResult()
        working_report = report

        for i in range(1, self.cfg.max_loops + 1):
            current = self.ingest(base_stem)
            vr = self.validate(working_report, reqs)

            if vr.passed:
                out = self.emit_version(working_report, base_stem, current)
                result.iterations.append(LoopIteration(
                    index=i, version_in=current.name if current else None,
                    version_out=out.name, passed=True,
                    validation_summary=vr.summary(), repaired=False,
                ))
                result.final_version = out
                result.converged = True
                self.audit.info("loop_converged", f"iteration {i} -> {out.name}")
                return result

            # Not passing: classify failures and attempt a structural repair.
            failure_types = sorted({iss.severity + ":" + iss.field for iss in vr.errors})
            self.audit.warn("iterate", f"iter={i} failures={failure_types}")

            repaired_path = None
            if current is not None:
                repaired_path = self.repair(current, base_stem)

            result.iterations.append(LoopIteration(
                index=i, version_in=current.name if current else None,
                version_out=repaired_path.name if repaired_path else None,
                passed=False, validation_summary=vr.summary(),
                repaired=repaired_path is not None,
                repair_fixes=[],
            ))

            if repaired_path is None:
                # No repair possible and validation failed -> escalate & stop.
                self.audit.escalate(
                    "loop_stalled",
                    f"iteration {i}: {len(vr.errors)} error(s) with no automated "
                    f"repair available. Escalating for human review.",
                )
                result.exhausted = True
                return result

            # A repair produced a new version -> re-ingest it so the next
            # iteration validates the *repaired* report, not the stale one.
            from .report_io import read_report
            try:
                working_report = read_report(repaired_path, section=self.cfg.section)
                self.audit.info("reingest", f"reloaded {repaired_path.name} for revalidation")
            except Exception as exc:
                self.audit.error("reingest_failed", f"{repaired_path.name}: {exc}")
                result.exhausted = True
                return result

        # The loop reloaded `working_report` from the last repair but the final
        # iteration ended before re-validating it. Give the repaired report one
        # last validation so a workbook that repairs into a passing state
        # converges instead of being wrongly reported as exhausted.
        final_vr = self.validate(working_report, reqs)
        if final_vr.passed:
            out = self.emit_version(working_report, base_stem,
                                    latest_version(self.cfg.final_reports, base_stem))
            result.iterations.append(LoopIteration(
                index=self.cfg.max_loops + 1,
                version_in=None, version_out=out.name, passed=True,
                validation_summary=final_vr.summary(), repaired=False,
            ))
            result.final_version = out
            result.converged = True
            self.audit.info("loop_converged", f"final revalidation -> {out.name}")
            return result

        result.exhausted = True
        self.audit.warn("loop_exhausted", f"reached max_loops={self.cfg.max_loops}")
        return result
