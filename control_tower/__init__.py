"""DataBossX Control Tower: a fail-closed control kernel for Section 32 work.

The tower polls exactly one pinned Drive folder, derives authority from folder
membership and hashes rather than from filenames, claims work exactly once
under a lease with monotonic fencing, spools evidence before any network call,
and verifies every upload by reading the exact bytes back.

Read-only is the default at every layer. Mutation requires an activated
mutation TaskEnvelope, and the HOLD cannot be removed by any code path here.
"""

from .constants import (
    HOLD,
    SENTINEL_BUILD_NOT_FOUND,
    SENTINEL_DRIVE_BLOCKED,
    SENTINEL_OWNER_DECISION,
    SENTINEL_REISSUE_BLOCKED,
    SENTINEL_TERMINALIZED,
    ControlTowerError,
)
from .drive import DriveClient, OfflineDriveClient, SafeDriveWriter
from .kernel import (
    AppendOnlySpool,
    ClaimLedger,
    FencingRegistry,
    LeaseRegistry,
    TaskEnvelope,
    claim_key,
    derive_authority,
)
from .tower import Gate0Runner, offline_canary, selftest

__all__ = [
    "HOLD",
    "SENTINEL_BUILD_NOT_FOUND",
    "SENTINEL_DRIVE_BLOCKED",
    "SENTINEL_OWNER_DECISION",
    "SENTINEL_REISSUE_BLOCKED",
    "SENTINEL_TERMINALIZED",
    "ControlTowerError",
    "DriveClient",
    "OfflineDriveClient",
    "SafeDriveWriter",
    "AppendOnlySpool",
    "ClaimLedger",
    "FencingRegistry",
    "LeaseRegistry",
    "TaskEnvelope",
    "claim_key",
    "derive_authority",
    "Gate0Runner",
    "offline_canary",
    "selftest",
]

__version__ = "1.0.0"
