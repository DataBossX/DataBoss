# Windows Remediation & Control Tower Verification Packet (v2)

**RELEASE STATE: FOR REVIEW - HOLD NO EXTERNAL RELEASE**
**SCOPE:** Authorized Windows Workstation (`RYANSPC` owning `C:\DataBoss`)
**GOVERNING RULING:** `DBX-RULING-R01-GATE0-COMMAND-SPENT-20260802T1213CDT`

---

## 1. Executive Summary & Mandatory Rules

This packet contains the exact, reproducible sequence of commands to be executed exclusively on the authorized Windows workstation.

### Invariants:
1. **DO NOT OPEN EXCEL.** Files must be audited and hashed by streaming raw bytes. Opening workbooks can trigger auto-recalculation, metadata corruption, or lock creation.
2. **THE ORIGINAL GATE 0 COMMAND IS RETIRED AND SPENT.** Do not attempt to claim, retry, or re-enter Drive ID `1C0C8ERuCYm6Rqso0ahLXMifhXqlYjinOlFkN5k29NCE`.
3. **ONE-WRITER KERNEL ONLY.** Maintain exactly one active lease, one monotonic fencing token, and one queue.
4. **HOLD IMMUTABILITY.** Every emitted receipt must carry `FOR REVIEW - HOLD NO EXTERNAL RELEASE`.

---

## 2. Step-by-Step Windows Execution Sequence

Open an administrative PowerShell or CMD prompt in the Windows repository checkout `C:\DataBoss`:

### Step 2.1: Preflight Kernel Selftest & Canary
Run the offline selftest to verify that all 26 control invariants hold on the Windows Python runtime:

```cmd
cd C:\DataBoss
run_control_tower.bat selftest
run_control_tower.bat canary
```
*Expected output:* `control_tower_selftest: 26/26 passed, 0 failed` and `control_tower_offline_canary: 7/7 passed, 0 failed`.

---

### Step 2.2: Execute Bridge-Restoration Envelope
Execute the owner-activated outbound-only bridge restoration:

```cmd
python -m control_tower.cli audit --drive --v12-path "C:\DataBoss\Section32\V12_Report.xlsx" --repo-path "C:\DataBoss"
```
*Envelope ID:* `TE-DBX-S32-BRIDGE-RESTORE-20260802T1043CDT`  
*Target Drive ID:* `159gQIvazu4RWDB8wmZSYuJxsEM9NC5gb`  
*Owner Activation:* `1MABO3IlrAeR6q4nxJLT7xSBeYiLQJdrL0cAUXaj8cqg`

Verify outbound-only operation, emit exactly one bridge terminal receipt with its `.sha256` sidecar, and stop after readback verification.

---

### Step 2.3: Process & Lease Remediation (Cures A & B)
1. **Quiesce / Bind Cursor Worker PID 49548:**
   Verify process status without workbook access:
   ```cmd
   tasklist /FI "PID eq 49548"
   ```
   Ensure no background process is holding workbook locks or competing for writes.

2. **Terminalize Containment Lease:**
   Append-only terminalize and release:
   `LEASE-DBX-V13-MULTI-WRITER-CONTAINMENT-20260801`

3. **Verify Zero Workbook Locks:**
   Ensure no `~$*.xlsx` lock files exist across `C:\DataBoss`.

---

### Step 2.4: Terminal Receipt Sidecar & Baseline Hashing (Cures D, F, G)
1. **Hash the Gate 0 Terminal Receipt Returned Bytes:**
   Drive ID: `1qwdfvWUGJiWmzEc6Ll4_BdD2z3kvcGwE`  
   Confirm SHA-256 is `52A969007216A3CE32305B030B520376734250B01CBB282C96451343A72C9708` (19,946 bytes) and publish its `.sha256` sidecar.

2. **Hash Protected Workbook Baselines (Read-Only Stream):**
   - **V12 Expected:** `D3937F46B3130A25719BB82CDAC702CECAA131BA5C5AACD4142BD346987D8D5D` (Confirm exact match; preserve unchanged)
   - **V13 Quarantined WIP Expected:** `FF8D6CF349CCEE753FA62F5213F152C0F3B17D7B18A57E1BA7A1A63DB6CEBC58`
   - **V10 Baseline:** `79668279F0CF1A49CDF6F599F611C7BE058D40D43FA54372F6B559E60D9E7F4C`
   - **V11 Baseline:** `81AE7941DC62C748CBAA57A0FCEEB77F24828440F3A954173284ED3DB0DB0369`

---

### Step 2.5: Authority Reconciliation & Successor Gate 0 Staging
Run authority reconciliation to confirm clean state:

```cmd
python -m control_tower.cli reconcile
```

Once all prerequisites pass, submit the Successor Gate 0 command draft (`1VfdAVRX8zG8Elzi_ucsOkM-Gy27JHrH_pitfg9oLY3E`) for owner activation before placing into `01_QUEUED`.

---

## 3. Terminal Sentinel Required

Upon successful completion of the successor Gate 0 run, emit:
`S32_SUCCESSOR_GATE0_CONTAINMENT_TERMINALIZED_CLEAN_AUTHORITY_DRAFT_READY`
