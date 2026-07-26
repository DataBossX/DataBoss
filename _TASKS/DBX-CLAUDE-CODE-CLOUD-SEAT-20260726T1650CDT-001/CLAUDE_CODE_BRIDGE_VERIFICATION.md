# CLAUDE CODE — BRIDGE VERIFICATION

**Timestamp:** 2026-07-26 17:08 CDT · **Task:** `DBX-CLAUDE-CODE-CLOUD-SEAT-20260726T1650CDT-001`
**Verdict: `PARTIAL_VERIFIED` — Drive channel proven byte-exact from this seat; worker execution
remains unproven and unobservable from here.**

---

## Canary — read → write → re-read → hash

Isolated task folder created (no shared/canonical path touched):
`DBX-CLAUDE-CODE-CLOUD-SEAT-20260726T1650CDT-001` — Drive ID `1_xQjtW0S3vD2MNfOyJ-fu-VQ-moPP4Go`

| Step | Result |
| --- | --- |
| 1. Compose payload locally | 235 bytes |
| 2. Source SHA-256 | `5774F33DBB9A9F5C815E534EF5205D55FF99C93A97204329442A2ABE81B3C7ED` |
| 3. Write to Drive | `CANARY__CLAUDE_CODE_CLOUD_SEAT__20260726T1650CDT.txt` → ID `1ssiLOXMb9GZARUXKZuYwTgEnCcZ_HtOv` |
| 4. Drive-reported size | 235 bytes — **matches** |
| 5. Re-read raw bytes from Drive | 235 bytes |
| 6. Re-read SHA-256 | `5774F33DBB9A9F5C815E534EF5205D55FF99C93A97204329442A2ABE81B3C7ED` |
| 7. Byte-identical comparison | **True** |

**Result: PASS.** Nonce `CLAUDE-CLOUD-20260726T1650CDT-9F2A7C41`.
`disableConversionToGoogleType=true` was set so the payload was stored as raw `text/plain` and not
silently converted to a Google-native Doc — the conversion trap that caused the 134-file
native-Doc blindness recorded in the prior 00R receipt.

## What this proves — and what it does not

**Proven from this seat:** authenticated Drive search, metadata read, content read, folder create,
file create, and **byte-exact read-back with hash equality**.

**Not proven, and not claimed:**

| Hop | Status |
| --- | --- |
| Local watcher observes the file | **UNPROVEN** — no visibility into the Windows host |
| Exactly-once claim | **UNPROVEN** |
| Isolated task folder created on the PC | **UNPROVEN** |
| Assigned agent reads the task | **UNPROVEN** — no headless Cursor/Codex worker CLI is installed (prior 00R BLOCKER-2) |
| Agent writes a real result | **UNPROVEN** |
| Terminal receipt published locally | **UNPROVEN** |

Queueing is not execution. This seat upholds the prior seat's refusal to upgrade
`PARTIAL_VERIFIED_EXACT_BLOCKER` to `PASS`, and adds: **two Claude seats agreeing does not
constitute independent confirmation of worker execution, because neither seat can observe the
workers.**

---

## LIMIT DISCOVERED — large binary payloads are not byte-transportable through this seat

**This is a real architectural constraint and it should be recorded in the control plane.**

Attempt: obtain the S17 workbook (25,561 bytes) as exact bytes to compute an independent SHA-256
and open the OOXML package.

| Step | Result |
| --- | --- |
| Drive returned the file as base64 | ~34,084 chars expected |
| Bytes reconstituted on this seat | **34,429 chars — corrupt** |
| `base64.b64decode` | failed: *"number of data characters (34429) cannot be 1 more than a multiple of 4"* |
| Duplicate-window scan (64-char stride) | no duplicated block — corruption was distributed |
| Disposition | **corrupt copy deleted; never used as evidence** |

**Root cause:** the payload must pass through the model context as a base64 string. That path is
not a byte-exact transport at 34 K characters. The 235-byte canary round-tripped perfectly, so the
**Drive channel and the MCP tools are not at fault** — the limit is context-mediated transcription
of large payloads.

**Consequences:**
1. This seat **cannot compute or verify SHA-256 of any workbook or PDF.** All hash arbitration
   (D-11) must occur on a seat with direct filesystem access to the bytes.
2. This seat **cannot perform OOXML package-integrity checks** — formulas, defined names,
   hyperlinks, print settings, embedded objects (S17 Pass 1, blocked).
3. Any envelope assigning hash verification or package-preserving edits to a `drive_only` seat
   **will fail or, worse, produce a fabricated-looking result.** It must be routed to a
   `windows_fs` seat.

**Recommended control-plane change:** add a required `requires:` capability field to every
TaskEnvelope — `windows_fs`, `native_excel`, `drive_only`, `byte_exact_io` — and refuse to
dispatch an envelope to a seat lacking the declared capability. The current envelopes address
"Claude Code" as one identity; at least two seats with different capabilities answer to that name
(see `CROSS_AGENT_DISAGREEMENT_REPORT.md` §5).

---

## Native-Doc blocker — status confirmed, unchanged

Google-native Docs remain unreadable to the local `drive_intake` path without an authorized export
adapter (prior 00R BLOCKER-1: `open()` on a `.gdoc` raises `OSError errno 22`; no OAuth credentials
set). The `STATUS__NATIVE-DOC-BLOCKED-*` files continue to accumulate in `1dPSvLNzXVYIbZ14hBmw8D9VmPJIvAtaI`,
which is the repaired intake behaving as designed — explicit blockers instead of silence.

Note the asymmetry worth exploiting: **this seat reads Google-native Docs without difficulty**
(all control documents for this report were read as native Docs). A `drive_only` Claude seat can
therefore serve as the export adapter for native-Doc directives without any new credential grant,
by reading a native Doc and republishing it as raw `.md`/`.txt` into the watched inbox — which is
exactly the "single next safest action" the prior 00R receipt identified.

**No credentials were read, requested, or created. No security control was weakened.**

## Release flags

`client_released=false` · `client_release_authorized=false` · `canonical_promotion_authorized=false`
`purchase_authorized=false` · `permanent_delete_authorized=false` · `title_artifacts_modified=false`
`leases_claimed_or_consumed=NONE`
