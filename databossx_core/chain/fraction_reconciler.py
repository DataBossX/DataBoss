"""
Fraction reconciler - reconciles fractional interests
"""

from decimal import Decimal
from typing import Dict, List
from ..models.chain import ChainNode


class FractionReconciler:
    """
    Reconciles fractional interests in ownership chains
    """

    def reconcile(self, nodes: List[ChainNode]) -> Dict:
        """
        Reconcile fractional interests

        Args:
            nodes: List of chain nodes

        Returns:
            Dictionary with reconciliation results
        """
        results = {
            "total_interest": Decimal(0),
            "by_owner": {},
            "discrepancies": [],
        }

        for node in nodes:
            total_fraction = Decimal(0)
            for ownership in node.ownerships:
                if ownership.fraction:
                    total_fraction += ownership.fraction

            if total_fraction > 0:
                results["by_owner"][node.entity_name] = {
                    "fraction": float(total_fraction),
                    "ownership_count": len(node.ownerships),
                }
                results["total_interest"] += total_fraction

                # Check for discrepancies
                if abs(total_fraction - Decimal(1.0)) > Decimal(0.01):
                    results["discrepancies"].append({
                        "owner": node.entity_name,
                        "expected": 1.0,
                        "actual": float(total_fraction),
                    })

        results["total_interest"] = float(results["total_interest"])
        return results
