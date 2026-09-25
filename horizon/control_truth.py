"""The Landman Helper control-truth projection.

Combines four independent fail-closed checks into one health projection for
a single section's finish-lane:

* source-identity retention (:mod:`horizon.source_identity_guard`)
* writer-gate exclusivity (:mod:`horizon.writer_gate`)
* OCR-vs-pixel source coverage (:mod:`horizon.source_coverage`)
* candidate byte/CRC/clean-cycle integrity (:mod:`horizon.package_gate`)

Nothing here hard-codes a client count, source name, or section identity --
every value comes from the caller's own ledgers, fixtures, or manifests.

Two projections are available:

* :meth:`ControlTruthProjection.internal_dict` -- full detail for local/CLI/
  operator tooling and tests. It can carry source identities and is never
  safe to serve from a public/site-facing endpoint.
* :meth:`ControlTruthProjection.public_dict` -- a compact, sanitized summary
  of counts and booleans only. It never includes source identities/
  filenames, legal descriptions, Drive/folder IDs, or any source content
  (see ``docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md``). This is the
  only projection a health API may return.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .package_gate import GateReport
from .source_coverage import CoverageSummary, coverage_summary
from .source_identity_guard import SourceIdentityGuardReport
from .writer_gate import WriterGateState


@dataclass
class CandidateIntegrity:
    """Byte/CRC/readback gate plus the clean-cycle streak on that exact SHA."""

    gate: GateReport
    clean_cycle_streak: int
    required_clean_cycles: int = 5

    @property
    def passed(self) -> bool:
        return self.gate.passed and self.clean_cycle_streak >= self.required_clean_cycles

    def as_dict(self) -> dict[str, Any]:
        return {
            "outer_sha256": self.gate.outer_sha256,
            "member_count": len(self.gate.members),
            "byte_gate_passed": self.gate.passed,
            "failures": list(self.gate.failures),
            "clean_cycle_streak": self.clean_cycle_streak,
            "required_clean_cycles": self.required_clean_cycles,
            "passed": self.passed,
        }


@dataclass
class ControlTruthProjection:
    section: str
    source_identity: SourceIdentityGuardReport
    writer_gate: WriterGateState
    coverage: CoverageSummary
    integrity: CandidateIntegrity

    @property
    def ready(self) -> bool:
        """READY requires every gate to pass on the same observation -- any
        single UNKNOWN, HOLD, or unresolved count keeps this False."""
        return (
            self.source_identity.passed
            and self.writer_gate.passed
            and self.coverage.fully_pixel_verified
            and self.coverage.unresolved == 0
            and self.integrity.passed
        )

    @property
    def status(self) -> str:
        return "READY" if self.ready else "HOLD"

    def internal_dict(self) -> dict[str, Any]:
        """Full detail for local/CLI/operator use. Do not serve this from a
        public/site-facing API -- see the module docstring."""
        return {
            "section": self.section,
            "status": self.status,
            "source_identity": self.source_identity.as_dict(),
            "writer_gate": self.writer_gate.as_dict(),
            "coverage": self.coverage.as_dict(),
            "integrity": self.integrity.as_dict(),
        }

    def public_dict(self) -> dict[str, Any]:
        """Compact, sanitized projection: counts and booleans only."""
        return {
            "section": self.section,
            "status": self.status,
            "source_identity_passed": self.source_identity.passed,
            "writer_gate_passed": self.writer_gate.passed,
            "writer_gate_reasons": list(self.writer_gate.reasons_denied()),
            "coverage": {
                "total": self.coverage.total,
                "pixel_verified": self.coverage.pixel_verified,
                "hold_count": self.coverage.hold_count,
                "unresolved": self.coverage.unresolved,
                "fully_pixel_verified": self.coverage.fully_pixel_verified,
            },
            "integrity": {
                "byte_gate_passed": self.integrity.gate.passed,
                "clean_cycle_streak": self.integrity.clean_cycle_streak,
                "required_clean_cycles": self.integrity.required_clean_cycles,
                "passed": self.integrity.passed,
            },
        }


def build_control_truth(
    section: str,
    *,
    source_identity: SourceIdentityGuardReport,
    writer_gate: WriterGateState,
    source_records: Iterable[dict[str, Any]],
    gate_report: GateReport,
    clean_cycle_streak: int,
    required_clean_cycles: int = 5,
) -> ControlTruthProjection:
    """Assemble one :class:`ControlTruthProjection` from fresh observations."""
    coverage = coverage_summary(source_records)
    integrity = CandidateIntegrity(
        gate=gate_report,
        clean_cycle_streak=clean_cycle_streak,
        required_clean_cycles=required_clean_cycles,
    )
    return ControlTruthProjection(
        section=section,
        source_identity=source_identity,
        writer_gate=writer_gate,
        coverage=coverage,
        integrity=integrity,
    )
