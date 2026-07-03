"""Sequential workflow runner with per-step audit logging.

A Workflow is an ordered list of named steps. Each step is a callable taking
the shared mutable *context* dict and returning any value (stored under the
step name). Execution stops at the first failure; the error is captured so the
run result is always a complete record of what happened.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

from app.logging_setup import get_logger

Step = Tuple[str, Callable[[Dict[str, Any]], Any]]


@dataclass
class StepResult:
    name: str
    ok: bool
    value: Any = None
    error: str | None = None


@dataclass
class RunResult:
    workflow: str
    results: List[StepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results)


class Workflow:
    def __init__(self, name: str, steps: List[Step] | None = None) -> None:
        self.name = name
        self.steps: List[Step] = list(steps or [])
        self.log = get_logger(f"workflow.{name}")

    def step(self, name: str, fn: Callable[[Dict[str, Any]], Any]) -> "Workflow":
        self.steps.append((name, fn))
        return self

    def run(self, context: Dict[str, Any] | None = None) -> RunResult:
        ctx: Dict[str, Any] = context if context is not None else {}
        result = RunResult(workflow=self.name)
        for name, fn in self.steps:
            self.log.info("step start: %s", name)
            try:
                value = fn(ctx)
                ctx[name] = value
                result.results.append(StepResult(name=name, ok=True, value=value))
                self.log.info("step ok: %s", name)
            except Exception as exc:  # noqa: BLE001 - we record and halt
                result.results.append(StepResult(name=name, ok=False, error=str(exc)))
                self.log.error("step failed: %s -> %s", name, exc)
                break
        return result
