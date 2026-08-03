# Test Results and Workflow Proof

FOR REVIEW - HOLD NO EXTERNAL RELEASE

- Python: 3.12.10
- pytest: 8.3.4
- Focused durable and B1-B7 repair suites after the fresh-store repair: 27 passed, exit 0
- Full Control Tower suite after the fresh-store repair: 155 passed, 2 skipped, exit 0
- Full repository `tests` directory after the fresh-store repair: 301 passed, 5 skipped, exit 0
- Windows process tests: 2 passed, exit 0
- Strict Flake8 fatal/import and changed-file checks: passed, zero findings
- Strict mypy on `control_tower/reconstruction.py` with skipped imports: passed, exit 0
- Full-tree strict typing: not certified; legacy modules have existing findings

The repair parent was `cb7917aca3268c33b0bafb6b47ac451ed7ff2a7c`. New regressions prove the exact original command and Drive identities remain unclaimable with a fresh store, after deleting the entire durable-state directory, and after relabelling the original Drive object. Empty live reconstruction pin sets now fail closed.

These are author-lane Linux results. They do not replace exact-head CI provenance or independent Windows `msvcrt`, process-race, and crash-recovery reproduction.

An earlier repository-root pytest collection attempt was not a passing proof because pre-existing generated test directories were inaccessible and optional dependencies were absent. The authoritative complete code-suite invocation is `pytest tests -q`.

No live Drive write, workbook write, merge, deployment, release, or hold removal occurred.
