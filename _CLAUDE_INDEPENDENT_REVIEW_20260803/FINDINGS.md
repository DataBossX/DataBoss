# Independent Control Tower Review — Findings

**Record class:** APPEND_ONLY_INDEPENDENT_REVIEW
**Release state:** FOR REVIEW - HOLD NO EXTERNAL RELEASE
**Reviewed heads (resolved dynamically, not taken from the brief):**

| PR | Head commit | State |
|---|---|---|
| #74 Control Tower | `39f1f404fe151171541f60fc00f9d455fdd4eeb5` | draft, unmerged, base `582d951` |
| #82 durable hardening (issue #78) | `92764fd2` | draft, unmerged |

**Environment:** Linux container, Python 3.11.15, no Windows host, no PyPI
reachability.

---

## 0. Scope correction that changes the recommendation

The brief directs review of PR #74. **PR #74 is superseded by PR #82**, which
adds `control_tower/durable.py` and `durable_runner.py`. Reviewing #74 alone
would have produced three blocking findings that #82 has already largely
closed. Findings below are therefore stated **per head**, and the surviving
live findings are those that hold against **#82**.

---

## 1. What genuinely verifies

Independently reproduced, not taken on report:

| Claim in PR #74 | Independent result |
|---|---|
| 119 tests pass | **CONFIRMED.** 119 collected, 119 passed, 0 failed, 0 errored |
| `selftest` 18/18, exit 0 | **CONFIRMED.** exit 0 |
| `canary` 7/7, exit 0, zero network | **CONFIRMED.** exit 0 |
| `audit` exit 2, `V12 NOT_VERIFIED_UNREACHABLE` | **CONFIRMED.** exit 2, `workbook opened: False` |
| PR #82 control-tower suites | **CONFIRMED.** 140 passed, 0 failed, 0 errored |

**Test-runner honesty:** `pytest` is **not installed** and `pip install pytest`
fails (`No matching distribution found` — no index reachability). These results
come from a **custom stdlib harness** (`harness/run_suite.py` plus a minimal
`pytest` shim providing `raises`, `mark.parametrize`, `fixture`, `tmp_path`,
`monkeypatch`). It collects the same 119 items and exercises the same
assertions, **but it is not upstream pytest and must never be reported as
such.** Behavioural differences in fixture teardown and parametrize id
generation are possible.

The design is genuinely strong in several places that deserve to be said
plainly: authority derives from pinned folder IDs rather than filenames;
`require_mutation_allowed(None)` raises so a forgotten envelope is never read
as permission; the ZIP-signature check catches an `.xlsx` renamed to `.json`;
and `canonical_drive_url()` rebuilds URLs from validated IDs instead of reusing
metadata `viewUrl`.

**That last control defends a live condition, not a theoretical one.** While
enumerating `02_RECEIPTS` I observed real Drive metadata whose `viewUrl` points
at `docichat.com` and `livepolls.app` — the exact hosts `DENIED_URL_HOSTS`
names. Confirmed on at least five current control records. The guard is
correctly aimed.

---

## 2. Findings

### F-01 — Exactly-once claim state does not survive a process restart
**Severity: BLOCKING against #74 · MITIGATED in #82 · file:** `control_tower/kernel.py` (`ClaimLedger`)

`ClaimLedger._claims` is a plain in-memory dict with no hydration from the
spool or from `02_RECEIPTS`.

*Failure scenario:* the tower issues the Gate 0 terminal, then the process
restarts (crash, reboot, scheduled-task restart). A fresh `ClaimLedger` has no
memory of the terminal, so the identical claim key reopens and a **second
terminal** is issued against a command that already holds one — precisely what
the 12:10 owner ruling forbids.

*Proof:* `harness/adversarial_durability.py`, check D1. In-process replay is
correctly refused; post-restart replay succeeds.

*In #82:* `_require_lease()` refuses any non-offline write unless
`durable_runner_bound` is true and the lease registry carries a durable
`store`. Live duplicate terminals are therefore prevented. **Residual
(MEDIUM):** the non-durable `ClaimLedger`/`FencingRegistry`/`LeaseRegistry`
remain exported and constructible from `kernel.py`, so the unsafe object is
still the easier one to reach for. My probe still confirms D1–D3 against #82
when those classes are used directly.

*Required correction:* hydrate durable state on construction, or make the
in-memory classes private/test-only so production cannot instantiate them.
*Regression test:* terminalise, discard the object, reconstruct from the same
root, assert the replayed claim raises `ClaimConflict`.

---

### F-02 — Monotonic fencing restarts at zero
**Severity: BLOCKING against #74 · MITIGATED in #82 · file:** `control_tower/kernel.py` (`FencingRegistry`)

`_highest` is in-memory. After a restart `next_sequence()` returns 1 again.

*Failure scenario:* run 1 reaches sequence 3. The process restarts and mints
sequence 1 — **lower than a token already issued**. The 12:10 ruling requires a
fencing token "strictly greater than any prior sequence for the scope". A
zombie holding sequence 3 and a fresh writer holding sequence 1 each pass
`require_strictly_current()` against their own registry.

*Proof:* check D2 (observed: run 1 highest = 3; post-restart reissue = 1).

*Required correction:* persist the high-water mark with the durable store and
seed `_highest` from it. *Regression test:* assert every issued sequence
strictly exceeds the persisted maximum across a simulated restart.

---

### F-03 — Two OS processes can each hold a valid lease for one scope
**Severity: BLOCKING against #74 · MITIGATED in #82 · file:** `control_tower/kernel.py` (`LeaseRegistry`)

`_active` is in-memory, so `acquire()` in a second process cannot see the
first process's lease. Both leases are unexpired; both pass `require_valid()`.
This defeats the "one active expiring writer lease" invariant.

*Proof:* check D3 — writer A (fence 4) and writer B (fence 2) simultaneously
valid on scope `S32_GATE0`.

*In #82:* the durable store arbitrates, and live writes are gated. Same
MEDIUM residual as F-01.

---

### F-04 — No production code path populates the retired-command register
**Severity: HIGH · LIVE IN BOTH #74 AND #82 · files:** `control_tower/constants.py`, `control_tower/durable.py`

This is the finding that survives review of the newest head, and it is the one
with a live trigger today.

- The 12:10 CDT owner ruling retired command
  `DBX-S32-CONTAINMENT-TERMINALIZE-AND-CLEAN-AUTHORITY-COMPILE-20260801T1846CDT`
  (`1C0C8ERuCYm6Rqso0ahLXMifhXqlYjinOlFkN5k29NCE`).
- **That document is still the sole physical child of the pinned queue folder**
  `1aLfAZdOvhAbBzg_pTluH12X4yoZ3u_JC` (verified by direct enumeration).
- PR #82 *does* add the mechanism: `durable.py` carries a `retired_commands`
  map, `retire()`, `is_retired()` and `reconcile(records, retired_command_ids)`.
- **But `retire()` and `reconcile()` are called from no production code path.**
  Verified: matches occur only in `durable.py` itself and in
  `tests/test_control_tower_durable.py`, where the retired ID exists solely as
  a test constant. `reconcile()` defaults `retired_command_ids` to empty.
- `constants.py` pins no retired-command list, and its only reference to the
  retired Drive ID is a URL-building test.

*Failure scenario:* an operator stands the tower up on the Windows host and
runs it against the live queue. Folder-membership-by-ID enumerates the retired
command as the sole candidate. Nothing consults `is_retired()` because nothing
ever populated the register. The tower presents a retired command as
executable — and the ruling's prohibition is enforced only by operator memory.

*Required correction:* pin the retired command ID(s) in `constants.py` as a
`RETIRED_COMMAND_IDS` frozenset, seed the durable store from it at startup, and
make queue enumeration consult `is_retired()` and skip with an explicit
`COMMAND_RETIRED` record. *Regression test:* place the retired ID in a synthetic
queue folder and assert enumeration yields zero candidates and emits the
retirement record. **Codex should fix this now** — it is small, bounded, and
directly guards the live prohibition.

---

### F-05 — Filename-suffix upload guard is bypassable by extension alone
**Severity: MEDIUM · file:** `control_tower/safety.py` (`assert_uploadable`)

Protection rests on three independent gates: pinned digest, filename suffix,
and mime prefix — plus the `PK` ZIP-signature check. For an OOXML workbook all
four are effective. But a **non-ZIP** client artifact (a `.txt` OCR dump, a raw
CSV renamed to `.json`, a JSON export of evidence rows) matches no pinned
digest, carries an allowed suffix, and has no `PK` header. It uploads.

*Failure scenario:* an evidence extract is spooled as `evidence_rows.json` and
leaves the boundary, because the guard enumerates *known-bad shapes* rather
than requiring *known-good content*.

*Required correction:* allowlist the record schemas the tower is permitted to
emit and reject any payload that does not validate against one. Defer if the
tower only ever emits kernel-generated records — but then assert that
structurally rather than relying on suffix denial. **Defer with an explicit
note**; not blocking for control-record-only traffic.

---

### F-06 — `assert_trusted_url` ignores port
**Severity: LOW · file:** `control_tower/safety.py`

`https://drive.google.com:8443/…` passes: `urlparse().hostname` strips the
port. Userinfo is handled correctly (`https://drive.google.com@evil.com/`
yields hostname `evil.com`, refused). Add `parsed.port in (None, 443)`.

---

### F-07 — `redact()` replaces the captured value everywhere in the match
**Severity: LOW · file:** `control_tower/safety.py`

`whole.replace(value, REDACTED)` is global within the matched span, so a value
that also appears as a substring of its own key over-redacts. Fails safe
(over-redaction, never under-redaction). The empty-value case is correctly
guarded, which would otherwise splice `[REDACTED]` between every character.

---

### F-08 — `FencingRegistry.require()` accepts an equal token
**Severity: LOW · file:** `control_tower/kernel.py`

`require()` returns successfully when `sequence == current`, with a comment
saying equality "is not good enough" — the comment describes a rejection the
code does not perform. `require_strictly_current()` (the write path) is
correct. Either make `require()` match its comment or reword it; as written a
future caller could reasonably trust the comment.

---

### F-09 — Cure letters are transposed against the ruling they satisfy
**Severity: MEDIUM (process, not code)**

Ruling letters A/B/C = Cursor PID / lease / bridge. Receipt letters A/B/C =
bridge / Cursor PID / lease. All eight subjects are covered, but "Cure C
complete" means different things in the two documents. Publish an append-only
crosswalk. Detail in `AUTHORITY_RECONCILIATION.md` §C-4.

---

### F-10 — Bridge activation expired with no terminal receipt
**Severity: BLOCKING (authority, not code)**

Full detail in `AUTHORITY_RECONCILIATION.md` §C-2. Cure C of the 12:10 ruling
is unmet and its authority lapsed at 2026-08-03 10:54 CDT. Requires a fresh
owner activation.

---

## 3. Test matrix status

Scenarios from the brief, and where each stands:

**Covered by the existing suites (verified passing):** duplicate command titles
with different Drive IDs; same command ID with different revision; terminal
without START/CLAIM; expired lease; lease valid but fence superseded; Drive
outage during receipt upload; readback bytes differ; local receipt before
network; adversarial filenames claiming APPROVED; non-Google URL; leaked token
in exception text; ZIP containing a workbook; workbook renamed to an allowed
suffix; path traversal; output outside allowed root; HOLD removal; spool
collision.

**Proven to FAIL by my probe (#74 head):** crash-restart duplicate terminal
(D1); fencing monotonicity across restart (D2); two writers racing for one
lease (D3); retired command still in queue (D4).

**Not reproducible from this lane, and not asserted:** Windows process, lock,
service and scheduled-task inspection; Excel lock probing; live Drive
integration; V10/V11/V12 hash re-verification; PID 49548 disposition;
duplicate-filename creation by live Drive; Google-native export drift.

---

## 4. Disposition for Codex

**Fix now:** F-04 (pin and enforce retired commands) — small, bounded, guards
a live prohibition. F-08 and F-06 — one-line corrections.

**Fix before any live run:** F-01/F-02/F-03 residual — make the non-durable
kernel classes unreachable from production, so the safe path is the only path.

**Defer with a written note:** F-05.

**Owner, not Codex:** F-09, F-10, and the four decisions in
`AUTHORITY_RECONCILIATION.md` §4.

**Recommend: PR #74 should not be treated as the canonical Control Tower head.
PR #82 supersedes it. Both remain draft and unmerged, as required.**

**FOR REVIEW - HOLD NO EXTERNAL RELEASE**
