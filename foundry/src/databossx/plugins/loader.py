"""Plugin discovery, validation, and (explicit-only) execution.

Validation never executes plugin code: manifests are parsed as JSON, and each
entrypoint's module file is checked by **AST inspection only** — the file must
parse and define the target function at module top level. Import/execution
happens exclusively inside :func:`call_entrypoint`, which is only reached by an
explicit ``databossx plugins run`` from the operator (or a smoke test).
"""

from __future__ import annotations

import ast
import importlib.util
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..errors import PluginError
from .manifest import PluginManifest, manifest_path, parse_manifest

log = logging.getLogger("databossx.plugins")


@dataclass
class LoadedPlugin:
    directory: Path
    manifest: Optional[PluginManifest] = None
    errors: List[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.manifest is not None and not self.errors

    @property
    def name(self) -> str:
        return self.manifest.name if self.manifest else self.directory.name


def _module_file(plugin_dir: Path, module: str) -> Path:
    return plugin_dir / (module.replace(".", "/") + ".py")


def _validate_entrypoint_ast(plugin_dir: Path, ep_name: str, target: str) -> List[str]:
    """Check the entrypoint resolves to a real top-level function — via AST only."""
    module, func = target.split(":", 1)
    path = _module_file(plugin_dir, module)
    if not path.is_file():
        return [f"entrypoint '{ep_name}': module file not found: {path}"]
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [f"entrypoint '{ep_name}': {path.name} has a syntax error: {exc}"]
    top_level = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if func not in top_level:
        return [
            f"entrypoint '{ep_name}': function {func!r} is not defined at the "
            f"top level of {path.name}"
        ]
    return []


def validate_plugin(plugin_dir: Path) -> LoadedPlugin:
    plugin_dir = Path(plugin_dir)
    loaded = LoadedPlugin(directory=plugin_dir)
    mpath = manifest_path(plugin_dir)
    if not mpath.is_file():
        loaded.errors.append(f"missing manifest: {mpath}")
        return loaded
    try:
        data = json.loads(mpath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        loaded.errors.append(f"{mpath}: invalid JSON: {exc}")
        return loaded
    manifest, errors = parse_manifest(data, source=str(mpath))
    loaded.errors.extend(errors)
    if manifest is None:
        return loaded
    if manifest.name != plugin_dir.name:
        loaded.errors.append(
            f"manifest name {manifest.name!r} does not match "
            f"directory name {plugin_dir.name!r}"
        )
    for ep_name, target in manifest.entrypoints.items():
        loaded.errors.extend(_validate_entrypoint_ast(plugin_dir, ep_name, target))
    if not loaded.errors:
        loaded.manifest = manifest
    return loaded


def discover_plugins(plugins_dir: Path) -> List[LoadedPlugin]:
    plugins_dir = Path(plugins_dir)
    if not plugins_dir.is_dir():
        return []
    found: List[LoadedPlugin] = []
    for child in sorted(plugins_dir.iterdir()):
        if child.is_dir() and manifest_path(child).is_file():
            found.append(validate_plugin(child))
    return found


def get_plugin(plugins_dir: Path, name: str) -> LoadedPlugin:
    plugin_dir = Path(plugins_dir) / name
    if not plugin_dir.is_dir():
        available = ", ".join(p.name for p in discover_plugins(plugins_dir)) or "<none>"
        raise PluginError(f"plugin {name!r} not found under {plugins_dir} "
                          f"(installed: {available})")
    loaded = validate_plugin(plugin_dir)
    if not loaded.valid:
        raise PluginError(
            f"plugin {name!r} failed validation:\n  " + "\n  ".join(loaded.errors)
        )
    return loaded


def call_entrypoint(
    plugins_dir: Path, ref: str, payload: Optional[Dict[str, Any]] = None
) -> Any:
    """Execute ``<plugin>:<entrypoint>`` with a JSON-able payload dict.

    This is the ONLY place plugin code is executed, and only ever on an
    explicit operator command. The entrypoint contract is
    ``def <func>(payload: dict) -> JSON-able result``.
    """
    if ":" not in ref:
        raise PluginError(f"plugin ref {ref!r} must be '<plugin>:<entrypoint>'")
    plugin_name, ep_name = ref.split(":", 1)
    loaded = get_plugin(plugins_dir, plugin_name)
    manifest = loaded.manifest
    assert manifest is not None  # get_plugin guarantees validity
    if ep_name not in manifest.entrypoints:
        raise PluginError(
            f"plugin {plugin_name!r} has no entrypoint {ep_name!r} "
            f"(declared: {', '.join(sorted(manifest.entrypoints))})"
        )
    module, func_name = manifest.entrypoints[ep_name].split(":", 1)
    path = _module_file(loaded.directory, module)

    module_key = f"databossx_plugin_{plugin_name}_{module.replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(module_key, path)
    if spec is None or spec.loader is None:
        raise PluginError(f"cannot load module {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_key] = mod
    # Let the plugin import sibling modules from its own directory.
    plugin_dir_str = str(loaded.directory)
    added_path = plugin_dir_str not in sys.path
    if added_path:
        sys.path.insert(0, plugin_dir_str)
    try:
        spec.loader.exec_module(mod)
        func = getattr(mod, func_name)
        log.info("running plugin entrypoint %s:%s", plugin_name, ep_name)
        return func(payload or {})
    except PluginError:
        raise
    except Exception as exc:
        raise PluginError(f"plugin {plugin_name}:{ep_name} raised: {exc}") from exc
    finally:
        if added_path and plugin_dir_str in sys.path:
            sys.path.remove(plugin_dir_str)
