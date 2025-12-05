"""
Chain graph analyzer - analyzes chain graphs for marketability and issues
"""

from datetime import datetime
from typing import List, Dict
from decimal import Decimal

from ..models.chain import ChainGraph, ChainAnalysis


class ChainGraphAnalyzer:
    """
    Analyzes chain-of-title graphs for marketability and issues
    """

    async def analyze(self, chain: ChainGraph) -> ChainAnalysis:
        """
        Analyze chain graph

        Args:
            chain: ChainGraph object

        Returns:
            ChainAnalysis object
        """
        # Check marketability
        is_marketable = await self._check_marketability(chain)
        marketability_issues = await self._identify_marketability_issues(chain)

        # Reconcile fractions
        fractional_reconciliation = await self._reconcile_fractions(chain)

        # Identify missing successors
        missing_successors = await self._identify_missing_successors(chain)

        # Identify unrecorded instruments
        unrecorded_instruments = await self._identify_unrecorded_instruments(chain)

        # Calculate confidence score
        confidence_score = await self._calculate_confidence(chain)

        return ChainAnalysis(
            chain_id=chain.id,
            is_marketable=is_marketable,
            marketability_issues=marketability_issues,
            fractional_reconciliation=fractional_reconciliation,
            missing_successors=missing_successors,
            unrecorded_instruments=unrecorded_instruments,
            confidence_score=confidence_score,
            analysis_date=datetime.utcnow(),
        )

    async def _check_marketability(self, chain: ChainGraph) -> bool:
        """Check if chain is marketable"""
        # Chain is marketable if:
        # 1. No critical gaps
        # 2. Fractions reconcile
        # 3. Clear current ownership

        critical_gaps = [g for g in chain.gaps if g.severity == "critical"]
        if critical_gaps:
            return False

        if not chain.current_owners:
            return False

        return True

    async def _identify_marketability_issues(self, chain: ChainGraph) -> List[str]:
        """Identify issues affecting marketability"""
        issues = []

        # Check for critical gaps
        critical_gaps = [g for g in chain.gaps if g.severity == "critical"]
        for gap in critical_gaps:
            issues.append(f"{gap.gap_type}: {gap.description}")

        # Check for missing current owners
        if not chain.current_owners:
            issues.append("No clear current owner identified")

        # Check for fractional issues
        warning_gaps = [g for g in chain.gaps if g.gap_type == "fractional_mismatch"]
        if warning_gaps:
            issues.append(f"Fractional interest mismatch detected ({len(warning_gaps)} instances)")

        return issues

    async def _reconcile_fractions(self, chain: ChainGraph) -> Dict:
        """Reconcile fractional interests"""
        reconciliation = {
            "total_fractional_interest": Decimal(0),
            "breakdown": {},
        }

        for node in chain.nodes:
            if node.is_current_owner:
                total_fraction = Decimal(0)
                for ownership in node.ownerships:
                    if ownership.fraction:
                        total_fraction += ownership.fraction

                if total_fraction > 0:
                    reconciliation["breakdown"][node.entity_name] = float(total_fraction)
                    reconciliation["total_fractional_interest"] += total_fraction

        reconciliation["total_fractional_interest"] = float(reconciliation["total_fractional_interest"])
        return reconciliation

    async def _identify_missing_successors(self, chain: ChainGraph) -> List[str]:
        """Identify likely missing successors/heirs"""
        missing = []

        # Look for probate-related gaps
        for gap in chain.gaps:
            if gap.gap_type == "missing_heir":
                missing.append(gap.description)

        return missing

    async def _identify_unrecorded_instruments(self, chain: ChainGraph) -> List[str]:
        """Identify likely unrecorded instruments"""
        unrecorded = []

        for gap in chain.gaps:
            if gap.gap_type == "missing_link":
                unrecorded.append(gap.description)

        return unrecorded

    async def _calculate_confidence(self, chain: ChainGraph) -> float:
        """Calculate overall confidence in chain analysis"""
        # Base confidence
        confidence = 0.8

        # Reduce for critical gaps
        critical_gaps = [g for g in chain.gaps if g.severity == "critical"]
        confidence -= len(critical_gaps) * 0.2

        # Reduce for warnings
        warning_gaps = [g for g in chain.gaps if g.severity == "warning"]
        confidence -= len(warning_gaps) * 0.05

        return max(0.0, min(1.0, confidence))
