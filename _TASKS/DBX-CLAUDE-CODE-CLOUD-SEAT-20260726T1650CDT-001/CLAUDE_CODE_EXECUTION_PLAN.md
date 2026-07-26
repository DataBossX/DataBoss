# CLAUDE CODE — EXECUTION PLAN

**Timestamp:** 2026-07-26 17:08 CDT · **Task:** `DBX-CLAUDE-CODE-CLOUD-SEAT-20260726T1650CDT-001`
**Parent:** `DBX-OVERNIGHT-TITLE-CONTINUATION-20260726T0106CDT-001` · Codex remains sole controller.

**This plan amends the 00W recovery order in two places, on evidence.** Everything else stands.

---

## AMENDMENT 1 — insert a lease-freeze ahead of lease reconciliation

00W Phase 2 assumes the A10 lease is sound and only needs a live executor. Evidence says the
lease's *target* is wrong in two independent ways:

- **D-01** — `Index!A10` reads as `Release of Oil and Gas Leases` from this seat, not
  `Order and Decree` (00W) and not `Quitclaim Deed` (the lease's own precondition).
- **D-02** — the Drive PENDING workbook contains **no `05ML-0463` row at all**; the lease is about
  an instrument that is not in that artifact.

Executing a one-cell write under a disputed row index, against a workbook that lacks the subject
instrument, risks silently destroying a correct classification in a client deliverable. The
lease's own fail-closed check (`A10 still equals Quitclaim Deed`) does **not** protect against
this: it protects against the value being wrong, not against two seats resolving `A10` to
different rows.

**New step 0:** Codex freezes `LEASE-S17-CURSOR-A10-20260726T1510CDT-001`, and re-issues it
targeting the instrument by **Doc No + Book-Page**, with the writer computing the cell address at
execution time and asserting the expected current value before write.

## AMENDMENT 2 — reorder Section 17 repair priority

00W treats A10 as the highest-value next move. **D-04 outranks it.** The `0285-0528` row asserts an
unqualified Warranty Deed of all of Section 17 to Carter Oil Company with an **empty Comments
field**, while the E1 face proves the grantors expressly reserved all oil, gas, coal and other
minerals. That is a live, evidence-confirmed misstatement of mineral title in a file already
staged in PENDING FINAL VERIFICATION. A10 is a classification refinement; D-04 is a wrong answer
about who owns the minerals.

---

## REVISED ORDER

| # | Action | Owner | Gate |
| --- | --- | --- | --- |
| 0 | **Freeze A10 lease** (D-01, D-02) | Codex | none — stop-work |
| 1 | Prove controller alive; close stale Cursor executor assignment | Codex | 00W Phase 2.1–2.2 |
| 2 | Drive canary | **DONE — PASS** (this seat) | byte-identical, §Bridge |
| 3 | Hash arbitration: reconcile `B19A6B97…` / `80A8D365…` / `B53B0876…` (D-11) | Codex `windows_fs` | one published lineage graph |
| 4 | **Repair `0285-0528` mineral-reservation warning (D-04)** | Codex writer, exact lease | E1 face already in hand |
| 5 | Re-baseline the S17 defect list against the artifact (D-03 is closed) | Claude Code `drive_only` | no lease needed |
| 6 | Section 20 read-only content audit | Claude Code `drive_only` | no lease needed |
| 7 | Section 32: hash the three copies; annotate PENDING as unrepaired (D-14) | Codex `windows_fs` | no content change |
| 8 | Pull faces for D-05..D-10 sequence anomalies + `030M-0595`, `030M-0615`, `05ML-0463`, `033M-0425` | Codex / county re-pull | D-15 |
| 9 | Re-issue corrected A10 lease by Doc No + Book-Page | Codex | after step 3 |
| 10 | Independent exact-byte validation of every repaired workbook | distinct Claude B seat | after each repair |
| 11 | Section 32 reconciliation via `horizon.controlled_loop` | Cursor + Codex | after step 7 and lineage freeze |
| 12 | Final readiness report; promote only when every gate passes | Codex + Ryan | **not reached** |

**Parallel-safe now:** steps 5, 6 (this seat) alongside 3, 4, 7 (Windows seat). No two agents write
the same workbook or task folder. This seat holds **no** writer lease and requests none.

---

## STANDING CONSTRAINTS — reaffirmed, not relaxed

- One controller (Codex), one authoritative queue, one status source. **No second command center,
  watcher, dispatcher, database, or prompt stack was created.** This seat created exactly one
  isolated Drive folder for its own read-only outputs.
- No agent writes outside its assigned task folder without an explicit lease.
- No direct overwrite of shared, canonical, staging, client-delivery, or final-report files.
- Promotion only by the authorized orchestrator, after schema + evidence + conflict + integrity +
  hash checks, independent review, read-back, and rollback preparation.
- Checks without a deterministic validator return `not_evaluated` and **block**. Absence of
  evidence is never a pass.
- Do not guess the contents of an unreadable instrument. Record the limitation, the paths searched,
  and the effect on status.

## CONTROL-PLANE REPAIR PROPOSED (one change, high leverage)

Add a required `requires:` capability field to every TaskEnvelope —
`windows_fs` · `native_excel` · `drive_only` · `byte_exact_io` — and refuse dispatch to a seat
lacking it. **Root cause it fixes:** 00W Phase 1 orders "Claude Code" to verify a `C:\DataBoss\…`
path, but at least two Claude Code seats answer to that name and one of them (this one) has no
Windows filesystem at all. Without a capability gate, such an envelope stalls silently or invites
a fabricated-looking result. See `CROSS_AGENT_DISAGREEMENT_REPORT.md` §5.

Secondary: one canonical envelope per task ID (D-17 — five 00W variants in 11 minutes), and an
adjacent `WATCHER_STATUS.INVALID` marker beside the known-false watcher record (D-18).

## HONEST FORECAST

**Probability all three sections reach evidence-backed client-ready state without new primary
sources: LOW.** The binding constraint is evidence, not tooling: ~99% of Section 17 rows have no
face binding, Section 20 is unaudited against its 136-instrument expectation, and Section 32's
144→140 discrepancy is unclassified. Repairing the bridge, the leases, and the workbooks — all
achievable — still leaves the abstracts source-limited.

The truthful attainable near-term state remains **`INTERNAL_REVIEW_SOURCE_LIMITED` /
`HOLD_NO_EXTERNAL_RELEASE`**. READY stays empty. That is the correct outcome, not a failure.
