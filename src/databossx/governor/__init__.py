"""Bounded Continuous Improvement Governor.

Finite, auditable cycles only. Never a second control plane, never an
unconstrained self-edit loop, never an autonomous release.
"""

from .cycle import run_synthetic_cycle
from .inventory import census_repository
from .policy_gate import scan_publication_policy
from .ranker import rank_proposals
from .tournament import judge_folders

__all__ = [
    "census_repository",
    "judge_folders",
    "rank_proposals",
    "run_synthetic_cycle",
    "scan_publication_policy",
]
