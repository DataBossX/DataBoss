"""FailureClassifier -- map raw findings onto the authoritative taxonomy.

Validators tag their findings with a best-guess category, but the taxonomy
(Section 6) is the single source of truth for *severity*, *repairability*, and
*routing*.  The classifier reconciles each finding against the taxonomy so the
RepairPlanner never has to re-derive intent, and so no validator can
accidentally mark an escalation-only category (e.g. a title chain gap) as
repairable.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..failure_taxonomy import TaxonomyEntry, entry_for
from ..models import Finding, Severity


@dataclass
class ClassifiedFinding:
    finding: Finding
    taxonomy: TaxonomyEntry

    @property
    def repairable(self) -> bool:
        # Repairable only if BOTH the taxonomy allows it AND the validator
        # produced a concrete, machine-verifiable repair hint.
        return self.taxonomy.repairable and self.finding.repairable \
            and bool(self.finding.repair_hint)

    @property
    def severity(self) -> Severity:
        return self.taxonomy.severity

    @property
    def route(self) -> str:
        return self.taxonomy.route


class FailureClassifier:
    def classify(self, findings: list[Finding]) -> list[ClassifiedFinding]:
        classified: list[ClassifiedFinding] = []
        for finding in findings:
            entry = entry_for(finding.category)
            # Force the finding's escalate/repairable flags into agreement with
            # the taxonomy so downstream routing is deterministic.
            if not entry.repairable:
                finding.repairable = False
                finding.escalate = True
            classified.append(ClassifiedFinding(finding=finding, taxonomy=entry))
        return classified
