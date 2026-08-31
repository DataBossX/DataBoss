"""Pinned constants and error types for the DataBossX Control Tower.

Every identifier here is a *pin*. Authority is derived from these values and
from cryptographic hashes -- never from a filename, a title, a timestamp, or
chat text. If a value is not pinned here, the kernel treats it as untrusted.
"""

HOLD = "FOR REVIEW - HOLD NO EXTERNAL RELEASE"

# --- Canonical Drive control package -------------------------------------
# These IDs are the ONLY folders the tower will read from or write to.
CONTROL_ROOT_FOLDER_ID = "1CGkVNw0jUExTTR7cACBsJ21YkSwtfqVL"
QUEUE_FOLDER_ID = "1aLfAZdOvhAbBzg_pTluH12X4yoZ3u_JC"
RECEIPTS_FOLDER_ID = "1G8qW5lQCSuT8nEvSTOzHFVdH-EN3r5yR"
STATUS_FOLDER_ID = "1y1UxIA9VaAqXfjkO1Bf-3W2M4FegCDdF"
BLOCKED_FOLDER_ID = "1VLvIH-_AgitAAndBBYMbtsJky-_k9i5Y"
COMPLETED_FOLDER_ID = "14EE_1aunpApmachFe6EMBVTX8zEUIoB_"
HUMAN_APPROVAL_FOLDER_ID = "1V8M9xwCsPZBdzPY-WTvvisyTV2EvIc6N"
WATCHER_OUTPUT_FOLDER_ID = "1EX7ye_MrwACJaS9f9E2bcSo7w4TW3kVC"

# The tower polls exactly one folder. Not a list, not a glob, not a name match.
POLLED_FOLDER_ID = QUEUE_FOLDER_ID

# Writes are permitted to these folders and no others.
ALLOWED_WRITE_FOLDER_IDS = frozenset({
    RECEIPTS_FOLDER_ID,
    WATCHER_OUTPUT_FOLDER_ID,
    STATUS_FOLDER_ID,
    BLOCKED_FOLDER_ID,
    HUMAN_APPROVAL_FOLDER_ID,
})

# Reads are permitted from these folders and no others.
ALLOWED_READ_FOLDER_IDS = frozenset(ALLOWED_WRITE_FOLDER_IDS | {
    CONTROL_ROOT_FOLDER_ID,
    QUEUE_FOLDER_ID,
    COMPLETED_FOLDER_ID,
})

# --- Drive Control Anchors -----------------------------------------------
LIVE_COO_CONTROL_DOC_ID = "1AaeCfzx1RWE_uXU2De2KOZHorBCxpxuAQqaK_6LFVJM"
RETIRED_GATE0_COMMAND_DRIVE_ID = "1C0C8ERuCYm6Rqso0ahLXMifhXqlYjinOlFkN5k29NCE"
RETIRED_GATE0_COMMAND_ID = "DBX-S32-CONTAINMENT-TERMINALIZE-AND-CLEAN-AUTHORITY-COMPILE-20260801T1846CDT"
RETIRED_GATE0_TERMINAL_RECEIPT_DRIVE_ID = "1qwdfvWUGJiWmzEc6Ll4_BdD2z3kvcGwE"
RETIRED_GATE0_TERMINAL_RECEIPT_SHA256 = "52A969007216A3CE32305B030B520376734250B01CBB282C96451343A72C9708"
OWNER_RULING_RETIRE_GATE0_DRIVE_ID = "1lgcSJItqzXZ-FbHt1Tm65Jly9WEv-imD33_QSzINXBM"
DRAFT_CLEAN_SUCCESSOR_GATE0_DRIVE_ID = "1VfdAVRX8zG8Elzi_ucsOkM-Gy27JHrH_pitfg9oLY3E"
CONDITIONAL_S32_COMPLETION_DRAFT_DRIVE_ID = "1yLvVqVGxmcFrYxXhWxRU-VUehg7cdvxut4fEZsGXPPg"
WINDOWS_REMEDIATION_PACKET_V2_DRIVE_ID = "1e7nFZjrHrxvXRnIGP2QD9yGj23oTeTZp"
BRIDGE_RESTORE_OWNER_ACTIVATION_DRIVE_ID = "1MABO3IlrAeR6q4nxJLT7xSBeYiLQJdrL0cAUXaj8cqg"
BRIDGE_RESTORE_ENVELOPE_ID = "TE-DBX-S32-BRIDGE-RESTORE-20260802T1043CDT"
BRIDGE_RESTORE_DRAFT_DRIVE_ID = "159gQIvazu4RWDB8wmZSYuJxsEM9NC5gb"

SPENT_COMMAND_DRIVE_IDS = frozenset({
    RETIRED_GATE0_COMMAND_DRIVE_ID,
})

SPENT_COMMAND_IDS = frozenset({
    RETIRED_GATE0_COMMAND_ID,
    "DBX-S32-CONTAINMENT-TERMINALIZE-AND-CLEAN-AUTHORITY-COMPILE-20260801T1846CDT",
})

# --- Protected baselines --------------------------------------------------
# A payload whose digest matches any of these is a protected client artifact
# and may never be uploaded through the tower.
V10_EXPECTED_SHA256 = "79668279F0CF1A49CDF6F599F611C7BE058D40D43FA54372F6B559E60D9E7F4C"
V11_EXPECTED_SHA256 = "81AE7941DC62C748CBAA57A0FCEEB77F24828440F3A954173284ED3DB0DB0369"
V12_EXPECTED_SHA256 = "D3937F46B3130A25719BB82CDAC702CECAA131BA5C5AACD4142BD346987D8D5D"
V9_EXPECTED_SHA256 = "7075B9AC8B9ACFEEBFA5FAE97A23B01064F2B19CC064AD4124B118900936B5A6"
V13_WIP_EXPECTED_SHA256 = "FF8D6CF349CCEE753FA62F5213F152C0F3B17D7B18A57E1BA7A1A63DB6CEBC58"
INVENTORY_EXPECTED_SHA256 = "648104BF819B3AA4B5E6F753C2677402A076C7F25B7CDB94799FD250C68249AD"

PROTECTED_WORKBOOK_SHA256 = frozenset({
    V10_EXPECTED_SHA256,  # V10
    V11_EXPECTED_SHA256,  # V11
    V12_EXPECTED_SHA256,  # V12
    V9_EXPECTED_SHA256,   # V9 advisory
    V13_WIP_EXPECTED_SHA256,  # V13 WIP
})

# Content types that are client artifacts or source evidence. The tower emits
# control records only; it never carries these payloads outward.
PROHIBITED_UPLOAD_SUFFIXES = frozenset({
    ".xlsx", ".xlsm", ".xltx", ".xls", ".pdf", ".zip", ".7z", ".rar",
    ".tif", ".tiff", ".jpg", ".jpeg", ".png", ".docx", ".doc", ".csv",
})

PROHIBITED_UPLOAD_MIME_PREFIXES = (
    "application/vnd.openxmlformats-",
    "application/vnd.ms-",
    "application/pdf",
    "application/zip",
    "image/",
)

# --- URL trust ------------------------------------------------------------
TRUSTED_URL_HOSTS = frozenset({
    "drive.google.com",
    "docs.google.com",
    "sheets.google.com",
    "www.googleapis.com",
})

# Hosts observed rewriting Drive viewUrl values. Explicitly denied so that a
# regression names them rather than silently widening the allowlist.
DENIED_URL_HOSTS = frozenset({
    "docichat.com",
    "www.docichat.com",
    "livepolls.app",
    "www.livepolls.app",
})

# --- Modes and sentinels --------------------------------------------------
MODE_READ_ONLY = "READ_ONLY"
MODE_MUTATION = "MUTATION"

SENTINEL_BUILD_NOT_FOUND = "DATABOSSX_CONTROL_TOWER_BUILD_NOT_FOUND"
SENTINEL_DRIVE_BLOCKED = "DATABOSSX_DRIVE_BRIDGE_BLOCKED_WITH_EXACT_CAUSE"
SENTINEL_TERMINALIZED = "S32_CONTAINMENT_TERMINALIZED_CLEAN_AUTHORITY_DRAFT_READY"
SENTINEL_SUCCESSOR_GATE0_CLEAN = "S32_SUCCESSOR_GATE0_CONTAINMENT_TERMINALIZED_CLEAN_AUTHORITY_DRAFT_READY"
SENTINEL_OWNER_DECISION = "S32_REQUIRES_OWNER_CONTROLLING_POINTER_DECISION"
SENTINEL_REISSUE_BLOCKED = "S32_AUTHORITY_REISSUE_COMPILATION_BLOCKED"

GATE0_TERMINAL_SENTINELS = frozenset({
    SENTINEL_TERMINALIZED,
    SENTINEL_SUCCESSOR_GATE0_CLEAN,
    SENTINEL_OWNER_DECISION,
    SENTINEL_REISSUE_BLOCKED,
})


class ControlTowerError(Exception):
    """Base class. Every guard failure is a subclass, so callers fail closed."""


class WriteDenied(ControlTowerError):
    """A write was attempted outside the approved folders."""


class ReadDenied(ControlTowerError):
    """A read was attempted outside the approved folders."""


class ProtectedArtifactUpload(ControlTowerError):
    """An upload carried protected workbook bytes or source evidence."""


class UntrustedUrl(ControlTowerError):
    """A URL on a non-Google host was supplied to a trusting call site."""


class HoldViolation(ControlTowerError):
    """An attempt was made to remove, alter, or omit the HOLD."""


class MutationDenied(ControlTowerError):
    """Mutation was attempted without an activated mutation TaskEnvelope."""


class ClaimConflict(ControlTowerError):
    """A second claim was attempted while a prior claim is unresolved."""


class LeaseExpired(ControlTowerError):
    """A write was attempted under a lease that is no longer valid."""


class FencingViolation(ControlTowerError):
    """A fencing sequence went backwards or repeated."""


class SpoolCollision(ControlTowerError):
    """An append-only spool write would have overwritten an existing record."""


class ReadbackMismatch(ControlTowerError):
    """Returned bytes did not match the uploaded bytes exactly."""


class AuthorityDenied(ControlTowerError):
    """Authority could not be derived from pinned identifiers."""


class RetiredCommandDenied(AuthorityDenied):
    """A spent or retired command was claimed, re-entered, or executed."""


class HeartbeatExpired(ControlTowerError):
    """A writer failed to emit a heartbeat within the required window."""


class StaleWriterDenied(ControlTowerError):
    """A stale or displaced writer attempted an operation."""


class StopFlagTriggered(ControlTowerError):
    """Execution was halted by an active emergency stop flag."""


class OutputNotAllowed(WriteDenied):
    """An output path or folder was outside the strict output allowlist."""


class StateMachineViolation(ControlTowerError):
    """An illegal lifecycle state transition was attempted."""

