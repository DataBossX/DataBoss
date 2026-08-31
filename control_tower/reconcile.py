"""Deterministic current-authority reconciliation for DataBossX Control Tower.

Produces a structured, reproducible authority report analyzing:
- Controlling owner rulings
- Active owner activations
- Retired / spent commands
- Terminalized commands
- Active drafts
- Expired authorizations
- Stale status documents
- Unresolved contradictions
- Protected hashes
- Exact next permitted action
- Exact prohibited actions
"""

import time

from .constants import (
    BRIDGE_RESTORE_DRAFT_DRIVE_ID,
    BRIDGE_RESTORE_ENVELOPE_ID,
    BRIDGE_RESTORE_OWNER_ACTIVATION_DRIVE_ID,
    CONDITIONAL_S32_COMPLETION_DRAFT_DRIVE_ID,
    DRAFT_CLEAN_SUCCESSOR_GATE0_DRIVE_ID,
    HOLD,
    INVENTORY_EXPECTED_SHA256,
    LIVE_COO_CONTROL_DOC_ID,
    OWNER_RULING_RETIRE_GATE0_DRIVE_ID,
    RETIRED_GATE0_COMMAND_DRIVE_ID,
    RETIRED_GATE0_COMMAND_ID,
    RETIRED_GATE0_TERMINAL_RECEIPT_DRIVE_ID,
    RETIRED_GATE0_TERMINAL_RECEIPT_SHA256,
    SENTINEL_OWNER_DECISION,
    SENTINEL_REISSUE_BLOCKED,
    SENTINEL_SUCCESSOR_GATE0_CLEAN,
    SENTINEL_TERMINALIZED,
    SPENT_COMMAND_DRIVE_IDS,
    SPENT_COMMAND_IDS,
    V10_EXPECTED_SHA256,
    V11_EXPECTED_SHA256,
    V12_EXPECTED_SHA256,
    V13_WIP_EXPECTED_SHA256,
    WINDOWS_REMEDIATION_PACKET_V2_DRIVE_ID,
)
from .safety import canonical_drive_url, canonical_json_bytes, sha256_hex, stamp_hold


def reconcile_authority(client=None, now=None):
    """Assemble deterministic authority analysis."""
    now_epoch = time.time() if now is None else float(now)

    report = {
        "schema": "databossx.authority_reconciliation_report.v1",
        "report_type": "AUTHORITY_RECONCILIATION",
        "created_at_epoch": now_epoch,
        "hold": HOLD,
        "governing_posture": "FAIL_CLOSED_ONE_WRITER_SOVEREIGN_CONTROL",

        "controlling_owner_rulings": [
            {
                "ruling_id": "DBX-RULING-R01-GATE0-COMMAND-SPENT-20260802T1213CDT",
                "title": "OWNER CONTROL RULING - SECTION 32 GATE 0 (COMMAND IS SPENT)",
                "drive_id": OWNER_RULING_RETIRE_GATE0_DRIVE_ID,
                "canonical_url": canonical_drive_url(OWNER_RULING_RETIRE_GATE0_DRIVE_ID),
                "author": "Ryan Lee Gille via ChatGPT Work",
                "status": "OPERATIVE_GOVERNING",
                "key_rulings": [
                    "Original Gate 0 command is permanently retired and spent",
                    "11:10 CDT BLOCKED receipt consumed the sole terminal slot",
                    "Missing START/CLAIM receipt remains a material control defect of record",
                    "Successor Gate 0 command requires new ID, new TaskEnvelope, new lease, next fencing token",
                    "All workbook mutations strictly prohibited until clean successor succeeds",
                ],
            }
        ],

        "active_owner_activations": [
            {
                "activation_id": "OWNER-ACTIVATION-BRIDGE-RESTORE-20260802T1043CDT",
                "drive_id": BRIDGE_RESTORE_OWNER_ACTIVATION_DRIVE_ID,
                "canonical_url": canonical_drive_url(BRIDGE_RESTORE_OWNER_ACTIVATION_DRIVE_ID),
                "envelope_id": BRIDGE_RESTORE_ENVELOPE_ID,
                "target_host": "AUTHORIZED_WINDOWS_WORKSTATION_ONLY",
                "scope": "SECTION32_BRIDGE_RESTORE",
                "status": "REQUIRES_WINDOWS_EXECUTION",
                "expiration_note": "Initial window 2026-08-03T10:54CDT; requires re-verification of validity before local execution",
            }
        ],

        "retired_and_spent_commands": [
            {
                "command_id": RETIRED_GATE0_COMMAND_ID,
                "drive_id": RETIRED_GATE0_COMMAND_DRIVE_ID,
                "canonical_url": canonical_drive_url(RETIRED_GATE0_COMMAND_DRIVE_ID),
                "terminal_receipt_drive_id": RETIRED_GATE0_TERMINAL_RECEIPT_DRIVE_ID,
                "terminal_receipt_sha256": RETIRED_GATE0_TERMINAL_RECEIPT_SHA256,
                "terminal_sentinel": SENTINEL_REISSUE_BLOCKED,
                "terminal_slot_consumed": True,
                "claimable": False,
                "reclaimable": False,
                "retriable": False,
                "status": "PERMANENTLY_RETIRED_AND_SPENT",
            }
        ],

        "terminalized_commands": [
            {
                "command_id": RETIRED_GATE0_COMMAND_ID,
                "terminal_receipt_drive_id": RETIRED_GATE0_TERMINAL_RECEIPT_DRIVE_ID,
                "outcome": "BLOCKED",
                "sentinel": SENTINEL_REISSUE_BLOCKED,
            }
        ],

        "active_drafts_and_staged_authority": [
            {
                "draft_id": "DRAFT-CLEAN-SUCCESSOR-GATE0-20260802",
                "drive_id": DRAFT_CLEAN_SUCCESSOR_GATE0_DRIVE_ID,
                "canonical_url": canonical_drive_url(DRAFT_CLEAN_SUCCESSOR_GATE0_DRIVE_ID),
                "status": "DRAFT_AWAITING_CURES_AND_OWNER_ACTIVATION",
                "in_queue": False,
                "executable": False,
                "prerequisites_met": "PARTIAL (Cloud deliverables ready; Windows cures pending)",
            },
            {
                "draft_id": "DRAFT-CONDITIONAL-S32-COMPLETION-20260802",
                "drive_id": CONDITIONAL_S32_COMPLETION_DRAFT_DRIVE_ID,
                "canonical_url": canonical_drive_url(CONDITIONAL_S32_COMPLETION_DRAFT_DRIVE_ID),
                "status": "LOCKED_BEHIND_GATE0_SUCCESSOR_CLEAN_TERMINAL",
                "executable": False,
            },
            {
                "draft_id": "DRAFT-BRIDGE-RESTORE-20260802",
                "drive_id": BRIDGE_RESTORE_DRAFT_DRIVE_ID,
                "canonical_url": canonical_drive_url(BRIDGE_RESTORE_DRAFT_DRIVE_ID),
                "envelope_id": BRIDGE_RESTORE_ENVELOPE_ID,
                "status": "AWAITING_WINDOWS_LOCAL_EXECUTION",
            },
            {
                "packet_id": "WINDOWS-REMEDIATION-PACKET-V2",
                "drive_id": WINDOWS_REMEDIATION_PACKET_V2_DRIVE_ID,
                "canonical_url": canonical_drive_url(WINDOWS_REMEDIATION_PACKET_V2_DRIVE_ID),
                "status": "READY_FOR_WINDOWS_OPERATOR",
            },
        ],

        "protected_baseline_hashes": {
            "V10_SHA256": V10_EXPECTED_SHA256,
            "V11_SHA256": V11_EXPECTED_SHA256,
            "V12_SHA256": V12_EXPECTED_SHA256,
            "V13_WIP_SHA256": V13_WIP_EXPECTED_SHA256,
            "INVENTORY_SHA256": INVENTORY_EXPECTED_SHA256,
        },

        "unresolved_contradictions": [
            {
                "contradiction_id": "C-01",
                "topic": "Spent command presence in queue folder",
                "detail": "Original retired Gate 0 command record may still reside as a child of 01_QUEUED on Drive; kernel fail-closed guards prevent claim, but physical archive to 04_BLOCKED is pending Windows operator action",
                "handling": "FAIL-CLOSED: Kernel derive_authority strictly rejects retired Drive ID and command ID",
            },
            {
                "contradiction_id": "C-02",
                "topic": "Terminal sentinel string naming in downstream completion draft",
                "detail": "Downstream completion draft refers to S32_CONTAINMENT_TERMINALIZED_CLEAN_AUTHORITY_DRAFT_READY while successor draft refers to S32_SUCCESSOR_GATE0_CONTAINMENT_TERMINALIZED_CLEAN_AUTHORITY_DRAFT_READY",
                "handling": "Both sentinels accepted in GATE0_TERMINAL_SENTINELS set for seamless alignment",
            },
        ],

        "exact_next_permitted_actions": [
            "1. (Cloud lane) Hardened Control Tower code and test suite committed and staged in Draft PR on bounded branch",
            "2. (Cloud lane) Prepare handoffs (CURSOR_TO_CHATGPT_HANDOFF.json and CURSOR_STATUS.md) and SHA-256 sidecars",
            "3. (Windows lane) Execute TE-DBX-S32-BRIDGE-RESTORE-20260802T1043CDT on authorized Windows PC",
            "4. (Windows lane) Quiesce / bind Cursor PID 49548 without workbook access",
            "5. (Windows lane) Terminalize and release LEASE-DBX-V13-MULTI-WRITER-CONTAINMENT-20260801",
            "6. (Windows lane) Hash returned bytes of 1qwdfvWUGJiWmzEc6Ll4_BdD2z3kvcGwE and publish .sha256 sidecar",
            "7. (Windows lane) Hash and verify V12 matches D3937F46...8D5D and V13 WIP matches FF8D6CF3...BC58",
            "8. (Owner) Review successor Gate 0 draft and grant explicit owner activation before queue placement",
        ],

        "exact_prohibited_actions": [
            "PROHIBITED: Claiming, reclaiming, retrying, or re-entering retired Gate 0 command 1C0C8ERuCYm6Rqso0ahLXMifhXqlYjinOlFkN5k29NCE",
            "PROHIBITED: Reconstructing a backdated START/CLAIM receipt for the spent command",
            "PROHIBITED: Issuing a second terminal receipt for the spent command",
            "PROHIBITED: Creating a competing queue, receipt root, policy engine, database, or agent platform",
            "PROHIBITED: Opening, recalculating, saving, or mutating Excel workbooks (V10, V11, V12, V13)",
            "PROHIBITED: Merging PRs, enabling auto-merge, or deploying outside draft review",
            "PROHIBITED: Removing or altering the HOLD sentinel on any control record",
            "PROHIBITED: Exposing credentials or committing unredacted secrets",
            "PROHIBITED: Claiming Windows-local verification from a cloud container",
        ],
    }

    stamped = stamp_hold(report)
    stamped["digest"] = sha256_hex(canonical_json_bytes(stamped))
    return stamped
