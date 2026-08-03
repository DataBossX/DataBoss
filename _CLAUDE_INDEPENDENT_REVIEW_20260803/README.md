# Claude Code — Independent Review Package (2026-08-03)

**FOR REVIEW - HOLD NO EXTERNAL RELEASE**

Read-only independent review. This lane is **not** a workbook writer, **not** a
second control plane, and issued **no** command claim or terminal.

| File | What it is |
|---|---|
| `AUTHORITY_RECONCILIATION.md` | Drive control-plane reconciliation and written authority ruling |
| `FINDINGS.md` | Control Tower code review, findings F-01..F-10 with severities and corrections |
| `CLAUDE_TO_CODEX_HANDOFF.json` | Machine-readable handoff to Codex |
| `CHATGPT_HANDOFF.json` | Single-file current state for ChatGPT |
| `REVIEW_RECEIPT.json` | Append-only review receipt |
| `SHA256SUMS.txt` | Reproducible sidecars for every file above |
| `harness/` | Independent test harness and adversarial durability probe |

## Reproducing

```
git worktree add /tmp/pr74 origin/pr/74 --detach
cd /tmp/pr74
PYTHONPATH=<this>/harness:. python3 <this>/harness/run_suite.py \
    tests/test_control_tower.py tests/test_control_tower_drive_google.py
PYTHONPATH=. python3 <this>/harness/adversarial_durability.py
```

`harness/pytest.py` is a **stdlib shim, not upstream pytest** — pytest is
unavailable in the review container and `pip install pytest` fails with no
index reachability. Results from it must never be reported as pytest results.

## Headline

- Controlling authority moved on 2026-08-03; the brief's anchors are stale.
- The bridge-restoration activation **expired 2026-08-03 10:54 CDT with no
  terminal receipt** — cure C is unmet and its authority lapsed.
- The retired Gate 0 command is **still the sole physical child of `01_QUEUED`**,
  and no production code path enforces a retirement tombstone (F-04).
- PR #74 is superseded by PR #82. Both remain draft and unmerged.
