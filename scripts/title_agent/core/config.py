"""Runtime configuration for the Title Agent.

Every path and tunable is environment-overridable so the same code that runs
in CI on Linux can point at ``D:\\Desktop\\DataBossX`` when executed on the
Examiner's Windows workstation. Nothing here is hard-coded to a single host.
"""

from __future__ import annotations

import os
from pathlib import Path

# The prospect this agent is commissioned for. These are facts about the deal,
# not tunables — they are asserted by the validators, never inferred.
PROSPECT_ID: str = "25-004"
SECTION: str = "31-12N-24W"
COUNTY: str = "Roger Mills"
STATE: str = "Oklahoma"
WELL_NAME: str = "Alexander 1-31"
TRACT_COUNT: int = 10
GROSS_ACRE_TARGET: float = 637.42

# Absolute tolerance for every mathematical gate. Interest conservation must
# net to exactly zero and acreage must foot to 637.42; we allow only binary
# floating-point dust below this threshold, nothing that a human would call
# a discrepancy.
DECIMAL_TOLERANCE: float = 1e-8

# Hard budget ceiling for OKCountyRecords spend. Reaching it halts the loop.
BUDGET_CAP_USD: float = 100.00


def _env_path(var: str, default: str) -> Path:
    return Path(os.getenv(var, default)).expanduser()


class Config:
    """Resolved runtime configuration.

    Instantiated once as the module-level ``config`` singleton. Re-read the
    environment by constructing a fresh ``Config`` if a test needs isolation.
    """

    def __init__(self) -> None:
        # Root under which all Title Agent state lives. On the Examiner's box
        # this would be set to ``D:/Desktop/DataBossX/scripts/title_agent``.
        self.BASE_DIR: Path = _env_path(
            "TITLE_AGENT_BASE_DIR", str(Path(__file__).resolve().parent.parent)
        )

        # SQLite state store: audit trail, version ledger, escalations, budget.
        self.DB_PATH: Path = _env_path(
            "TITLE_AGENT_DB_PATH", str(self.BASE_DIR / "state" / "title_agent.db")
        )

        # Where minted, versioned workbooks are written. Never overwritten.
        self.WORKBOOK_DIR: Path = _env_path(
            "TITLE_AGENT_WORKBOOK_DIR", str(self.BASE_DIR / "state" / "workbooks")
        )

        # Where certification artifacts (Certified Workbook + Audit Report) go.
        self.REPORTS_DIR: Path = _env_path(
            "TITLE_AGENT_REPORTS_DIR", str(self.BASE_DIR / "state" / "reports")
        )

        # Human-readable append-only mirror of the audit log.
        self.AUDIT_LOG_PATH: Path = _env_path(
            "TITLE_AGENT_AUDIT_LOG", str(self.BASE_DIR / "state" / "audit.log")
        )

        self.BUDGET_CAP_USD: float = float(
            os.getenv("TITLE_AGENT_BUDGET_CAP", str(BUDGET_CAP_USD))
        )

        # OKCountyRecords source-verification API.
        self.OKCOUNTY_API_BASE_URL: str = os.getenv(
            "OKCOUNTY_API_BASE_URL", "https://api.okcountyrecords.com/v1"
        ).rstrip("/")
        # Basic Auth: the API key is sent as the username with an empty
        # password, per the OKCounty scheme. Read at call time so a key rotated
        # in the environment takes effect without a restart.
        self.OKCOUNTY_API_KEY_ENV: str = os.getenv(
            "OKCOUNTY_API_KEY_ENV", "OKCOUNTY_API_KEY"
        )
        self.OKCOUNTY_COST_PER_IMAGE: float = float(
            os.getenv("OKCOUNTY_COST_PER_IMAGE", "0.50")
        )
        self.OKCOUNTY_COST_PER_SEARCH: float = float(
            os.getenv("OKCOUNTY_COST_PER_SEARCH", "0.10")
        )
        # curl timeout, seconds. Cloudflare-fronted endpoints can be slow.
        self.OKCOUNTY_CURL_TIMEOUT: int = int(
            os.getenv("OKCOUNTY_CURL_TIMEOUT", "30")
        )

    def ensure_dirs(self) -> None:
        """Create the state directories if absent. Idempotent."""
        for path in (self.DB_PATH.parent, self.WORKBOOK_DIR, self.REPORTS_DIR,
                     self.AUDIT_LOG_PATH.parent):
            path.mkdir(parents=True, exist_ok=True)


config = Config()
