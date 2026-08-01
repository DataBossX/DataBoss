"""DataBossX Command Center control kernel.

Release state: FOR REVIEW - HOLD - NO EXTERNAL RELEASE.

This package is the single canonical control kernel for the Command Center
lane. It is deliberately dependency-free (Python standard library only) so it
can be executed and tested inside an air-gapped runner. See
``docs/command_center/adr/ADR-0001-zero-dependency-stack.md``.
"""

from __future__ import annotations

SCHEMA_VERSION = "1.0.0"
POLICY_VERSION = "policy-2026-08-01.1"

__all__ = ["SCHEMA_VERSION", "POLICY_VERSION"]
