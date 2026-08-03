"""Adversarial proofs against PR #74 head 39f1f40.

Each check below asserts the DEFECT is present. A check that prints DEFECT
CONFIRMED means the guarantee PR #74 claims does not hold across a process
restart. If a future commit fixes the defect, these checks will print
DEFECT ABSENT and exit non-zero, which is the intended regression signal.

Nothing here touches Drive, a workbook, or any client evidence.
"""

import sys

from control_tower.kernel import ClaimLedger, FencingRegistry, LeaseRegistry, claim_key
from control_tower.constants import ClaimConflict

SCOPE = "S32_GATE0"
RETIRED_CMD = "DBX-S32-CONTAINMENT-TERMINALIZE-AND-CLEAN-AUTHORITY-COMPILE-20260801T1846CDT"
RETIRED_DRIVE_ID = "1C0C8ERuCYm6Rqso0ahLXMifhXqlYjinOlFkN5k29NCE"

results = []


def check(name, defect_present, detail):
    results.append((name, defect_present, detail))
    print("[{0}] {1}\n      {2}\n".format(
        "DEFECT CONFIRMED" if defect_present else "DEFECT ABSENT", name, detail))


# -- D1: exactly-once claim state does not survive a restart ---------------
ledger_run1 = ClaimLedger()
key = claim_key(RETIRED_CMD, RETIRED_DRIVE_ID, "4")
ledger_run1.open(key, "writer-A", 1000.0)
ledger_run1.resolve(key, "S32_AUTHORITY_REISSUE_COMPILATION_BLOCKED")

# Same process: a second terminal is correctly refused.
try:
    ledger_run1.open(key, "writer-A", 1001.0)
    same_process_blocked = False
except ClaimConflict:
    same_process_blocked = True

# Process restart: a brand-new ledger has no memory of the terminal.
ledger_run2 = ClaimLedger()
replayed = ledger_run2.open(key, "writer-B", 2000.0)
ledger_run2.resolve(key, "S32_AUTHORITY_REISSUE_COMPILATION_BLOCKED")

check(
    "D1 duplicate terminal after restart",
    same_process_blocked and replayed["state"] == "OPEN",
    "ClaimLedger._claims is an in-memory dict with no hydration from the "
    "spool or 02_RECEIPTS. In-process replay refused={0}; after restart the "
    "identical claim key reopened and issued a SECOND terminal for a command "
    "that already holds one.".format(same_process_blocked),
)

# -- D2: monotonic fencing restarts at zero -------------------------------
fence_run1 = FencingRegistry()
for _ in range(3):
    fence_run1.next_sequence(SCOPE)
high_before = fence_run1.highest(SCOPE)

fence_run2 = FencingRegistry()
seq_after_restart = fence_run2.next_sequence(SCOPE)

check(
    "D2 fencing sequence is not monotonic across restarts",
    seq_after_restart < high_before,
    "Run 1 reached sequence {0}. After restart the registry reissued "
    "sequence {1}, which is LOWER. The owner ruling requires a token "
    "'strictly greater than all prior tokens'.".format(high_before, seq_after_restart),
)

# -- D3: two live writers each believe they hold the current fence --------
lease_run1 = LeaseRegistry(fencing=fence_run1)
lease_a = lease_run1.acquire(SCOPE, "writer-A", now=1000.0, ttl_seconds=3600)
a_ok = lease_run1.require_valid(lease_a, now=1010.0) is not None

lease_run2 = LeaseRegistry(fencing=fence_run2)  # fresh process, no shared state
lease_b = lease_run2.acquire(SCOPE, "writer-B", now=1020.0, ttl_seconds=3600)
b_ok = lease_run2.require_valid(lease_b, now=1030.0) is not None

# Writer A's lease is still unexpired and still passes ITS registry.
a_still_ok = lease_run1.require_valid(lease_a, now=1030.0) is not None

check(
    "D3 two concurrent writers both pass require_valid for one scope",
    a_ok and b_ok and a_still_ok,
    "LeaseRegistry._active is in-memory. Writer A (fence {0}) and writer B "
    "(fence {1}) hold simultaneously-valid leases on scope {2}, and each "
    "passes require_strictly_current against its own registry. Nothing "
    "arbitrates between two OS processes.".format(
        lease_a.fencing_sequence, lease_b.fencing_sequence, SCOPE),
)

# -- D4: no retirement/tombstone concept exists ---------------------------
import control_tower.constants as C

tombstone_surface = [
    n for n in dir(C)
    if any(t in n.upper() for t in ("RETIRE", "TOMBSTONE", "SPENT", "REVOK", "SUPERSED"))
]
check(
    "D4 no retired-command tombstone pin",
    not tombstone_surface,
    "constants.py exposes no retired/spent/revoked command register. The "
    "owner ruling of 2026-08-02 12:10 CDT retired command {0} (Drive ID {1}), "
    "and that document is still the SOLE physical child of the pinned queue "
    "folder. Folder-membership-by-ID therefore still presents it as "
    "executable.".format(RETIRED_CMD, RETIRED_DRIVE_ID),
)

confirmed = sum(1 for _, d, _ in results if d)
print("=" * 68)
print("ADVERSARIAL DURABILITY PROBE - defects confirmed: {0}/{1}".format(
    confirmed, len(results)))
print("=" * 68)
sys.exit(0 if confirmed == len(results) else 1)
