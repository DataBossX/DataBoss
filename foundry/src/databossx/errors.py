"""Typed error hierarchy for the Foundry.

Every command-level failure raises a :class:`FoundryError` subclass carrying
an ``exit_code`` so the CLI can translate exceptions into process exit codes
without string matching.
"""

from __future__ import annotations


class FoundryError(Exception):
    """Base error for all Foundry failures. Exit code 1 by default."""

    exit_code = 1


class DoctorUnclean(FoundryError):
    """The environment is missing required tools. Doctor exits nonzero until clean."""

    exit_code = 2


class ProjectNotFound(FoundryError):
    """The named project does not exist under the projects root."""


class EnvError(FoundryError):
    """Virtualenv creation/repair failed."""


class PlanError(FoundryError):
    """PLAN.md is missing, malformed, or does not declare the requested task."""


class TaskFailed(FoundryError):
    """A task step exited nonzero or timed out; outputs were rolled back."""


class PluginError(FoundryError):
    """A plugin manifest is invalid or an entrypoint cannot be resolved."""
