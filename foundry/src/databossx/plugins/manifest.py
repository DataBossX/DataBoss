"""The ``plugin.json`` manifest spec.

Every plugin lives in its own directory under ``/plugins`` and MUST carry a
``plugin.json``:

.. code-block:: json

    {
      "name": "safety_kernel",
      "version": "1.0.0",
      "description": "What the plugin does.",
      "entrypoints": {"smoke": "entry:smoke"},
      "permissions": ["filesystem:read", "filesystem:write"],
      "requires": {"tools": ["tesseract"], "python": ["pydantic>=2"]}
    }

* ``name`` — slug, must match the plugin directory name.
* ``version`` — semantic version ``MAJOR.MINOR.PATCH``.
* ``entrypoints`` — map of public entrypoint name to ``module:function``
  (module is a ``.py`` path relative to the plugin dir, dots for subpackages).
* ``permissions`` — declared capabilities, from a closed vocabulary; anything
  undeclared is a validation error so a human reviews what a plugin may do.
* ``requires.tools`` — doctor tool keys the plugin needs on the machine.
* ``requires.python`` — pip requirement strings for the plugin's own deps.

Parsing collects *all* problems instead of stopping at the first one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ALLOWED_PERMISSIONS = {
    "filesystem:read",
    "filesystem:write",
    "subprocess",
    "network",
}

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_ENTRYPOINT_RE = re.compile(r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")


@dataclass(frozen=True)
class PluginManifest:
    name: str
    version: str
    description: str
    entrypoints: Dict[str, str] = field(default_factory=dict)
    permissions: Tuple[str, ...] = ()
    requires_tools: Tuple[str, ...] = ()
    requires_python: Tuple[str, ...] = ()


def parse_manifest(
    data: object, source: str = "plugin.json"
) -> Tuple[Optional[PluginManifest], List[str]]:
    """Validate raw JSON data; returns ``(manifest_or_None, errors)``."""
    errors: List[str] = []
    if not isinstance(data, dict):
        return None, [f"{source}: manifest must be a JSON object"]

    name = data.get("name")
    if not isinstance(name, str) or not _NAME_RE.match(name):
        errors.append(f"{source}: 'name' must be a slug (got {name!r})")

    version = data.get("version")
    if not isinstance(version, str) or not _VERSION_RE.match(version):
        errors.append(f"{source}: 'version' must be MAJOR.MINOR.PATCH (got {version!r})")

    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append(f"{source}: 'description' is required")

    entrypoints = data.get("entrypoints")
    if not isinstance(entrypoints, dict) or not entrypoints:
        errors.append(f"{source}: 'entrypoints' must be a non-empty object")
        entrypoints = {}
    else:
        for ep_name, target in entrypoints.items():
            if not isinstance(ep_name, str) or not _NAME_RE.match(ep_name):
                errors.append(f"{source}: entrypoint name {ep_name!r} is not a slug")
            if not isinstance(target, str) or not _ENTRYPOINT_RE.match(target):
                errors.append(
                    f"{source}: entrypoint {ep_name!r} target must be "
                    f"'module:function' (got {target!r})"
                )

    permissions = data.get("permissions", [])
    if not isinstance(permissions, list):
        errors.append(f"{source}: 'permissions' must be a list")
        permissions = []
    else:
        for perm in permissions:
            if perm not in ALLOWED_PERMISSIONS:
                errors.append(
                    f"{source}: unknown permission {perm!r} "
                    f"(allowed: {sorted(ALLOWED_PERMISSIONS)})"
                )

    requires = data.get("requires", {})
    if not isinstance(requires, dict):
        errors.append(f"{source}: 'requires' must be an object")
        requires = {}
    tools = requires.get("tools", [])
    pythons = requires.get("python", [])
    for label, seq in (("requires.tools", tools), ("requires.python", pythons)):
        if not isinstance(seq, list) or not all(isinstance(x, str) for x in seq):
            errors.append(f"{source}: '{label}' must be a list of strings")

    unknown = set(data) - {"name", "version", "description", "entrypoints",
                           "permissions", "requires"}
    for key in sorted(unknown):
        errors.append(f"{source}: unknown top-level key {key!r}")

    if errors:
        return None, errors
    return (
        PluginManifest(
            name=name,
            version=version,
            description=description.strip(),
            entrypoints=dict(entrypoints),
            permissions=tuple(permissions),
            requires_tools=tuple(tools if isinstance(tools, list) else ()),
            requires_python=tuple(pythons if isinstance(pythons, list) else ()),
        ),
        [],
    )


def manifest_path(plugin_dir: Path) -> Path:
    return Path(plugin_dir) / "plugin.json"
