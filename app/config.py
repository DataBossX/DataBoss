"""DataBossX configuration loader (stdlib-only).

Loads non-secret settings from config/settings.toml and reads secrets ONLY from
the process environment, on demand. It never parses .env files and never logs or
returns raw secret values — callers get presence booleans or redacted strings.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - depends on interpreter version
    tomllib = None  # type: ignore
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "config" / "settings.toml"

# Secret env var names DataBossX may use. Values are never stored on the config
# object — we only ever check presence or fetch on demand.
SECRET_KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "SUPABASE_KEY")


@dataclass
class Config:
    settings: dict[str, Any] = field(default_factory=dict)
    root: Path = ROOT

    def get(self, *keys: str, default: Any = None) -> Any:
        """Nested lookup, e.g. cfg.get('llms', 'extractor')."""
        node: Any = self.settings
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def has_secret(self, name: str) -> bool:
        return bool(os.environ.get(name))

    def secret_status(self) -> dict[str, bool]:
        """Map of secret name -> present? — safe to log (no values)."""
        return {k: self.has_secret(k) for k in SECRET_KEYS}

    @staticmethod
    def redact(value: str | None) -> str:
        """Render a secret as e.g. 'sk_****' — never the real value."""
        if not value:
            return "<unset>"
        head = value[:3]
        return f"{head}{'*' * max(4, len(value) - 3)}"


def load_config(settings_path: Path | None = None) -> Config:
    path = settings_path or SETTINGS_PATH
    settings: dict[str, Any] = {}
    if path.exists() and tomllib is not None:
        with open(path, "rb") as fh:
            settings = tomllib.load(fh)
    return Config(settings=settings)
