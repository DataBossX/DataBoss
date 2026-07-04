"""Central configuration for the DataBossX validation agent.

Loads paths and environment, enforces the economic and iteration caps that are
system laws, and provides safe (secret-redacting) config dumps.

The specification targets a Windows host rooted at ``D:\\Desktop\\DataBossX``.
To remain runnable on non-Windows CI / cloud environments, all roots are
resolved from environment variables first and fall back to the location of this
package on disk. Nothing here ever depends on a hard-coded absolute path.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # python-dotenv is optional at import time; enforced by healthcheck
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - defensive
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:  # type: ignore
        return False


# --------------------------------------------------------------------------- #
# Hard system-law limits. These are ceilings, never raised at runtime.
# --------------------------------------------------------------------------- #
ABSOLUTE_API_CAP_USD: Decimal = Decimal("100.00")
ABSOLUTE_MAX_ITERATIONS: int = 5

_SECRET_KEY_MARKERS = ("PASSWORD", "SECRET", "TOKEN", "APIKEY", "API_KEY", "KEY")
_REDACTED = "***REDACTED***"


def _package_agent_root() -> Path:
    # config/settings.py -> config -> validation_agent
    return Path(__file__).resolve().parent.parent


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_decimal(name: str, default: Decimal) -> Decimal:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return Decimal(raw.strip())
    except (InvalidOperation, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def is_secret_key(key: str) -> bool:
    upper = key.upper()
    return any(marker in upper for marker in _SECRET_KEY_MARKERS)


@dataclass(frozen=True)
class Settings:
    """Immutable, validated runtime configuration."""

    databossx_root: Path
    agent_root: Path
    outputs_dir: Path
    db_path: Path

    api_cap_usd: Decimal
    max_iterations: int
    dry_run: bool
    live_source_mode: bool
    auto_approve_paid_docs: bool
    per_document_auto_approval_limit_usd: Decimal

    libreoffice_path: Optional[Path]
    extra_source_dirs: List[Path] = field(default_factory=list)

    # Non-secret operational knobs
    expected_acreage_total: Decimal = Decimal("637.42")
    expected_tract_count: int = 10

    # Secrets are stored but never emitted by ``as_safe_dict``.
    _okcounty_username: Optional[str] = None
    _okcounty_password: Optional[str] = None
    _okcounty_api_base_url: Optional[str] = None

    # ---- credential accessors (never logged) ---- #
    @property
    def okcounty_username(self) -> Optional[str]:
        return self._okcounty_username

    @property
    def okcounty_password(self) -> Optional[str]:
        return self._okcounty_password

    @property
    def okcounty_api_base_url(self) -> Optional[str]:
        return self._okcounty_api_base_url

    def has_okcounty_credentials(self) -> bool:
        return bool(
            self._okcounty_username
            and self._okcounty_password
            and self._okcounty_api_base_url
        )

    def missing_okcounty_credentials(self) -> List[str]:
        missing: List[str] = []
        if not self._okcounty_username:
            missing.append("OKCOUNTY_USERNAME")
        if not self._okcounty_password:
            missing.append("OKCOUNTY_PASSWORD")
        if not self._okcounty_api_base_url:
            missing.append("OKCOUNTY_API_BASE_URL")
        return missing

    def paid_source_access_allowed(self) -> bool:
        """Paid/external access requires live mode AND credentials."""
        return (
            self.live_source_mode
            and not self.dry_run
            and self.has_okcounty_credentials()
        )

    def source_search_dirs(self) -> List[Path]:
        """Ordered, de-duplicated list of folders searched for source docs."""
        candidates: List[Path] = [
            self.databossx_root,
            self.outputs_dir,
            self.databossx_root / "reports",
            self.databossx_root / "workbooks",
            self.databossx_root / "documents",
        ]
        candidates.extend(self.extra_source_dirs)
        seen: set[str] = set()
        ordered: List[Path] = []
        for path in candidates:
            key = str(path)
            if key not in seen:
                seen.add(key)
                ordered.append(path)
        return ordered

    def as_safe_dict(self) -> Dict[str, Any]:
        """Config dump with all secrets redacted. Safe for logs/UI."""
        return {
            "databossx_root": str(self.databossx_root),
            "agent_root": str(self.agent_root),
            "outputs_dir": str(self.outputs_dir),
            "db_path": str(self.db_path),
            "api_cap_usd": str(self.api_cap_usd),
            "max_iterations": self.max_iterations,
            "dry_run": self.dry_run,
            "live_source_mode": self.live_source_mode,
            "auto_approve_paid_docs": self.auto_approve_paid_docs,
            "per_document_auto_approval_limit_usd": str(
                self.per_document_auto_approval_limit_usd
            ),
            "libreoffice_path": str(self.libreoffice_path)
            if self.libreoffice_path
            else None,
            "extra_source_dirs": [str(p) for p in self.extra_source_dirs],
            "expected_acreage_total": str(self.expected_acreage_total),
            "expected_tract_count": self.expected_tract_count,
            "okcounty_username": _REDACTED if self._okcounty_username else None,
            "okcounty_password": _REDACTED if self._okcounty_password else None,
            "okcounty_api_base_url": self._okcounty_api_base_url or None,
            "okcounty_credentials_present": self.has_okcounty_credentials(),
            "paid_source_access_allowed": self.paid_source_access_allowed(),
        }


def _detect_libreoffice(explicit: Optional[str]) -> Optional[Path]:
    if explicit and explicit.strip():
        candidate = Path(explicit.strip())
        if candidate.exists():
            return candidate
        # keep configured value even if unresolved here; runner re-checks
        return candidate
    common = [
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
        Path("/usr/bin/soffice"),
        Path("/usr/bin/libreoffice"),
        Path("/opt/libreoffice/program/soffice"),
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
    ]
    for path in common:
        if path.exists():
            return path
    return None


def _parse_extra_dirs(raw: Optional[str]) -> List[Path]:
    if not raw or not raw.strip():
        return []
    parts = [p.strip() for p in raw.replace(";", os.pathsep).split(os.pathsep)]
    return [Path(p) for p in parts if p]


def load_settings(env_file: Optional[Path] = None) -> Settings:
    """Load and validate settings from the environment / ``.env`` file.

    Enforces the two hard system laws: API cap must be <= 100.00 and max
    iterations must be <= 5. Values exceeding the ceiling are clamped down
    (never up), so a misconfigured ``.env`` can never loosen protection.
    """

    agent_root = _package_agent_root()
    if env_file is None:
        env_file = agent_root / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)

    root_raw = os.environ.get("DATABOSSX_ROOT", "").strip()
    agent_raw = os.environ.get("DATABOSSX_AGENT_ROOT", "").strip()

    # On non-Windows hosts a configured "D:\..." path is unusable, so fall back
    # to the on-disk package location when the configured path does not exist.
    databossx_root = Path(root_raw) if root_raw else agent_root.parent.parent
    if root_raw and not Path(root_raw).exists():
        databossx_root = agent_root.parent.parent

    resolved_agent_root = Path(agent_raw) if agent_raw else agent_root
    if agent_raw and not Path(agent_raw).exists():
        resolved_agent_root = agent_root

    outputs_dir = resolved_agent_root / "outputs"
    db_path = resolved_agent_root / "db" / "databossx_agent.sqlite3"

    api_cap = _env_decimal("DATABOSSX_API_CAP_USD", ABSOLUTE_API_CAP_USD)
    if api_cap > ABSOLUTE_API_CAP_USD or api_cap <= 0:
        api_cap = ABSOLUTE_API_CAP_USD

    max_iters = _env_int("DATABOSSX_MAX_ITERATIONS", ABSOLUTE_MAX_ITERATIONS)
    if max_iters > ABSOLUTE_MAX_ITERATIONS or max_iters < 1:
        max_iters = ABSOLUTE_MAX_ITERATIONS

    per_doc_limit = _env_decimal(
        "DATABOSSX_PER_DOCUMENT_AUTO_APPROVAL_LIMIT_USD", Decimal("0.00")
    )
    if per_doc_limit < 0:
        per_doc_limit = Decimal("0.00")

    settings = Settings(
        databossx_root=databossx_root,
        agent_root=resolved_agent_root,
        outputs_dir=outputs_dir,
        db_path=db_path,
        api_cap_usd=api_cap,
        max_iterations=max_iters,
        dry_run=_env_flag("DATABOSSX_DRY_RUN", True),
        live_source_mode=_env_flag("DATABOSSX_LIVE_SOURCE_MODE", False),
        auto_approve_paid_docs=_env_flag("DATABOSSX_AUTO_APPROVE_PAID_DOCS", False),
        per_document_auto_approval_limit_usd=per_doc_limit,
        libreoffice_path=_detect_libreoffice(os.environ.get("LIBREOFFICE_PATH")),
        extra_source_dirs=_parse_extra_dirs(
            os.environ.get("DATABOSSX_EXTRA_SOURCE_DIRS")
        ),
        _okcounty_username=os.environ.get("OKCOUNTY_USERNAME") or None,
        _okcounty_password=os.environ.get("OKCOUNTY_PASSWORD") or None,
        _okcounty_api_base_url=os.environ.get("OKCOUNTY_API_BASE_URL") or None,
    )
    return settings


# Convenience singleton for callers that just want defaults.
_DEFAULT: Optional[Settings] = None


def get_settings(reload: bool = False) -> Settings:
    global _DEFAULT
    if _DEFAULT is None or reload:
        _DEFAULT = load_settings()
    return _DEFAULT
