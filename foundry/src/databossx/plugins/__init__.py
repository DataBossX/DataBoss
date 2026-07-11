"""Plugin system: manifest spec and a loader that validates without executing.

Core code never imports plugins. Plugin code is only ever executed on an
explicit ``databossx plugins run <plugin>:<entrypoint>`` invocation; manifest
loading and validation are pure data + AST inspection.
"""

from .manifest import ALLOWED_PERMISSIONS, PluginManifest, parse_manifest  # noqa: F401
from .loader import LoadedPlugin, call_entrypoint, discover_plugins, validate_plugin  # noqa: F401
