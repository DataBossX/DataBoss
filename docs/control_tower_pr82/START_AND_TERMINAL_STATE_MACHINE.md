# START and Terminal State Machine

FOR REVIEW - HOLD NO EXTERNAL RELEASE

START: `ABSENT -> CLAIM_PREPARED -> OPEN`. Retirement, noncanonical identity, malformed authority, ACK replay, or competing lease fails before `CLAIM_PREPARED`. The prepared payload and digest are immutable. An expired lease uses explicit recovery with a higher fence and reuses the frozen START bytes; it never emits a second logical START.

Terminal: `OPEN -> TERMINAL_PREPARED -> TERMINAL_UPLOADED -> RESOLVED`. Exact lease identity, holder, scope, fence, envelope digest, and ACK identity are validated inside the preparation transaction. The writer revalidates before create, after byte readback, before recording upload, and before resolution. A network-window supersession leaves an explicit orphan for reconciliation and never resolves the claim.

Historical receipts are append-only. No transition removes the review hold.
