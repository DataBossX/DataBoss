# Rollback

FOR REVIEW - HOLD NO EXTERNAL RELEASE

The repair is isolated to branch `agent/issue-78-durable-control-tower`. The immutable pre-repair remote head is `92764fd2f7ddf41710634b9b8d712f44ca2d6882`; the repair base is `39f1f404fe151171541f60fc00f9d455fdd4eeb5`.

Rollback is code-only: create a new revert commit for the exact repair commit after Cursor/control-plane reconciliation. Do not reset a shared worktree and do not delete append-only receipts. No database, workbook, PDF, evidence, status pointer, or Drive object must be restored because this lane does not mutate those protected assets.

Private Gate 0 control-state rollback evidence is retained outside the code repository and is referenced by the private terminal receipt.
