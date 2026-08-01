# WORKSPACE RECEIPTS — Phase 0 isolation

- Receipt set ID: `DBX-WORKSPACE-RECEIPTS-2026-08-01`
- Produced: 2026-08-01
- All four workspaces exist and are empty of competitor work. **No writer has
  been started in any of them.**

---

## Common facts

| Field | Value |
| --- | --- |
| Fork point for every workspace | `582d95161cf8220fb37f5224e21e57dcc5c3121c` |
| Isolation mechanism | `git worktree` — separate HEAD, index, and working tree per entry |
| Files changed by any competitor so far | 0 |
| Commits by any competitor so far | 0 |
| Tests run inside any workspace so far | 0 |
| Branches pushed to `origin` | 0 |
| Simulated components | none yet — no prototype exists |

## ENTRY-A

| Field | Value |
| --- | --- |
| Stance | Reliability-and-security-first architecture |
| Branch | `tournament/entry-a-reliability-security` |
| Worktree | `/home/user/tournament-workspaces/entry-a` |
| HEAD at creation | `582d95161cf8220fb37f5224e21e57dcc5c3121c` |
| `git status` at creation | clean |
| State | CREATED — NOT LAUNCHED |

## ENTRY-B

| Field | Value |
| --- | --- |
| Stance | Mobile-product-and-operator-experience-first architecture |
| Branch | `tournament/entry-b-mobile-operator` |
| Worktree | `/home/user/tournament-workspaces/entry-b` |
| HEAD at creation | `582d95161cf8220fb37f5224e21e57dcc5c3121c` |
| `git status` at creation | clean |
| State | CREATED — NOT LAUNCHED |

## ENTRY-C

| Field | Value |
| --- | --- |
| Stance | Data-intelligence-and-property-graph-first architecture |
| Branch | `tournament/entry-c-data-intelligence` |
| Worktree | `/home/user/tournament-workspaces/entry-c` |
| HEAD at creation | `582d95161cf8220fb37f5224e21e57dcc5c3121c` |
| `git status` at creation | clean |
| State | CREATED — NOT LAUNCHED |

## ENTRY-D (optional entry)

| Field | Value |
| --- | --- |
| Stance | Deliberately unconventional architecture |
| Branch | `tournament/entry-d-unconventional` |
| Worktree | `/home/user/tournament-workspaces/entry-d` |
| HEAD at creation | `582d95161cf8220fb37f5224e21e57dcc5c3121c` |
| `git status` at creation | clean |
| State | CREATED — NOT LAUNCHED |

## Isolation probe result

See `COMPETITOR_REGISTRY.md` §3 for the executed cross-contamination probe and
for the explicit statement of what this isolation does **not** cover (shared
container, shared filesystem, no per-entry sandbox, database/port isolation
still to be assigned before Phase 2).

## Teardown

`git worktree remove <path>` plus `git branch -D <branch>` reverses all of this.
Nothing here has touched `main`, `origin`, or any application file.
