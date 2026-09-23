# Receipt schema, hash chain, and terminal states

Every cycle produces exactly one `Receipt`, defined in `evolution_loop.py`.
This document is the spec for that record: its fields, how the ledger it
lives in is protected, and the full catalog of terminal states it can
carry. Per the blueprint's rule #12 ("Complete audit"), a receipt must be
enough, on its own plus the stage hashes it references, to reconstruct
*why* the cycle ended the way it did.

## Fields

```python
@dataclass(frozen=True)
class Receipt:
    receipt_id: str                       # "receipt-<16 hex>"
    cycle_id: str                         # "cycle-<16 hex>", shared by every
                                           # stage of one run_cycle() call
    created_at: str                       # ISO-8601 UTC
    terminal_state: TerminalState         # exactly one value, see below
    proposal_id: str | None               # None only for NO_ELIGIBLE_PROPOSAL
    proposal_hash: str | None             # ImprovementProposal.proposal_hash
    envelope_hash: str | None             # TaskEnvelope.envelope_hash, if reached
    authorization_id: str | None          # Authorization.authorization_id, if issued
    stage_hashes: dict[str, str]          # {"observe": ..., "propose": ...,
                                           #  "prioritize": ..., "authorize": ...,
                                           #  "build": ..., "test": ...,
                                           #  "adversarial": ...} -- only the
                                           # stages actually reached are present
    notes: tuple[str, ...]                # human-readable reasons; never the
                                           # sole record of *why* -- always
                                           # paired with a stage_hashes entry
    previous_receipt_hash: str | None     # the prior line's _receipt_hash,
                                           # None only for the first line ever
                                           # written to a given ledger file
```

`receipt.receipt_hash` (a property, not a stored field) is
`content_hash(asdict(receipt))` — the canonical-JSON SHA-256 of every field
above. It is computed fresh each time it is accessed, so it can never drift
from the fields it describes.

## The ledger file: append-only, hash-chained JSONL

`ReceiptLedger` (in `evolution_loop.py`) writes one line per receipt to
`receipts.jsonl`:

```json
{"chain_hash": "<sha256 hex>", "receipt": { ...Receipt fields..., "_receipt_hash": "<sha256 hex>" }}
```

- `_receipt_hash` is the `receipt_hash` computed at write time, stored
  alongside the payload.
- `chain_hash` is `sha256(previous_chain_hash_or_empty_string + _receipt_hash)`.
  The first line in a file has `previous_chain_hash = ""`.

### Two independent checks, both required (`verify_chain()`)

1. **Content integrity** — for every line, recompute
   `content_hash(receipt_payload_without_"_receipt_hash")` and compare it to
   the stored `_receipt_hash`. This catches someone editing a field (say,
   changing `terminal_state` from `REJECTED_ADVERSARIAL` to
   `PROMOTED_DRAFT_PR_ELIGIBLE`) while leaving the stored hash string alone.
2. **Chain linkage** — recompute
   `sha256(previous_chain_hash + stored_receipt_hash)` and compare it to the
   stored `chain_hash`. This catches reordering, deleting, or inserting
   whole lines, even if each individual line's own content hash still
   matches itself.

Both checks are exercised by `test_evolution_loop.py`
(`ReceiptLedgerTests`), including a regression test that specifically edits
a field's *value* without touching `_receipt_hash` — the failure mode the
chain-only check (an earlier draft of this ledger) missed.

### `append()` refuses to heal a broken chain

```python
def append(self, receipt: Receipt) -> str:
    if not self.verify_chain():
        raise AuditChainCompromised(...)
    ...
```

If the existing file already fails `verify_chain()`, `append()` raises
`AuditChainCompromised` instead of writing a new line that would make a
future full-file scan look "mostly fine." The module's CLI (`main()`)
catches this at the top level and exits with status `2`, printing the
reason to `stderr`. There is no `--force` flag and no "repair the ledger"
function anywhere in this module — matches the blueprint's rule #8
("Approval binds hashes... any change invalidates the previous approval")
and issue #68's explicit prohibition on editing audit history.

## Terminal states

Every `Receipt.terminal_state` is exactly one of:

| State | Meaning | Reachable from |
| --- | --- | --- |
| `PROMOTED_DRAFT_PR_ELIGIBLE` | Every gate passed: canary test passed, all adversarial probes passed. Means "a human may now open a **draft** PR referencing this receipt" — nothing more. | ADVERSARIAL (all probes pass) |
| `NO_ELIGIBLE_PROPOSAL` | OBSERVE produced zero observations, or the ranked list is empty. Not an error. | PROPOSE (empty) or PRIORITIZE (empty input) |
| `VETOED` | The top-ranked proposal carried one or more hard-veto reasons. `notes` lists them. | PRIORITIZE |
| `SKIPPED_DUPLICATE` | Reserved for a caller-level dedup check before even building a `PrioritizeContext` (the in-cycle duplicate check surfaces as `VETOED` with a `duplicate_terminal_proposal` reason instead; this state is available for an external scheduler that wants to short-circuit even earlier). | external caller |
| `AUTHORIZATION_DENIED_SCOPE` | `authorize()` refused — either the proposal was not actually eligible, or it requested more than `AutonomyLevel.L2`. Acts as a second gate behind PRIORITIZE's veto. | AUTHORIZE |
| `AUTHORIZATION_EXPIRED` | The authorization's TTL elapsed before BUILD ran. | BUILD (entry check) |
| `REJECTED_SANDBOX_ESCAPE` | BUILD (or anything it calls) attempted to resolve a path outside the authorized sandbox root. | BUILD |
| `REJECTED_BUILD_UNVERIFIABLE` | The invented canary test failed, timed out, or could not run. | TEST |
| `REJECTED_ADVERSARIAL` | At least one control probe in ADVERSARIAL failed. `notes` lists the failing `probe_id`s. | ADVERSARIAL |
| `AUDIT_CHAIN_COMPROMISED` | Not stored *in* a receipt (there is no valid ledger to append to) — instead raised as `AuditChainCompromised` and surfaced by the CLI as exit code `2`. Listed here because it is a valid outcome of trying to run a cycle. | RECEIPT (pre-append check) |

`LEARNABLE_TERMINAL_STATES` (used by the LEARN stage, see
`LEARNING_MEMORY.md`) is the subset
`{PROMOTED_DRAFT_PR_ELIGIBLE, REJECTED_ADVERSARIAL,
REJECTED_BUILD_UNVERIFIABLE, VETOED}` — the four states with a specific,
attributable reason. The remaining states describe a system-level failure
(lock contention, authorization plumbing, tamper detection) rather than a
fact about the *proposal*, and are quarantined unconditionally regardless
of review.

## Example receipt (from an actual `--mode full` smoke run)

```json
{
  "receipt_id": "receipt-226b47be4fda48bc",
  "cycle_id": "cycle-2465a78678fa4db6",
  "created_at": "2026-09-23T19:52:41Z",
  "terminal_state": "PROMOTED_DRAFT_PR_ELIGIBLE",
  "proposal_id": "prop-0f2028f652e5c7ac",
  "proposal_hash": "397fff3625835bafa546b1c420cded04a456a62acec7cdfe250517a2c4798e00",
  "envelope_hash": "a0327c4b1c498d63675255848f4df3f6ba9e93d8b367c1966c9771cd39fda7fc",
  "authorization_id": "auth-dd783c4326674aae",
  "stage_hashes": {
    "observe": "90608f088b3c340727b56655172c7b678b39bd510998c90f3117fe6585094ccb",
    "propose": "dd138a8d6b0b1ef34fe03e1ba7855459f1b9b44503b949d6e581a47f7689ec34",
    "prioritize": "17c9c7ba07b092e1aaf702a484ce70fcea68743391833eca1fc59efe6f8f3259",
    "authorize": "9151dec25abe8b9aa2f5af1961471ea86760dccee471d01d736d1166582eff2c",
    "build": "2d6425feb66aab2db2291c25253014886880ebfb1aa01b8e34da905ab01f6e89",
    "test": "20176176d9bafbd0dcc3b84bb2bdfb8edb366a297ee64d1c2d013aee5362b40e",
    "envelope": "a0327c4b1c498d63675255848f4df3f6ba9e93d8b367c1966c9771cd39fda7fc",
    "adversarial": "dabfe9cfdbe854e60088b1fab0b445153fb1a3d187af3fa3eee7c4661a3e3849"
  },
  "notes": ["all gates passed; eligible for a human-opened draft PR only"],
  "previous_receipt_hash": null
}
```

Note what is *absent*: no file contents, no client evidence, no secrets, no
raw model confidence score treated as fact, and no claim beyond "eligible
for a human-opened draft PR." The adversarial probe detail (which probes
ran and why each passed) lives in the `CycleResult.adversarial_outcome`
returned by `run_cycle()` / printed by the CLI — the receipt's
`stage_hashes["adversarial"]` binds to that detail without duplicating it,
keeping the ledger line itself small and stable.
