"""Minimal tool registry — name -> callable, with metadata.

Agents and workflows resolve tools by name so wiring stays declarative.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict


@dataclass
class Tool:
    name: str
    fn: Callable
    description: str = ""


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, name: str, fn: Callable, description: str = "") -> None:
        if name in self._tools:
            raise ValueError(f"Tool already registered: {name}")
        self._tools[name] = Tool(name=name, fn=fn, description=description)

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"No such tool: {name}")
        return self._tools[name]

    def call(self, name: str, *args, **kwargs):
        return self.get(name).fn(*args, **kwargs)

    def names(self) -> list[str]:
        return sorted(self._tools)


# A process-wide default registry for convenience.
registry = ToolRegistry()
