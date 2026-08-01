# COMPETITOR REGISTRY

- Registry ID: `DBX-COMPETITOR-REGISTRY-2026-08-01`
- Status: **ROSTER PROPOSED — NOT LAUNCHED.** No competitor has been started, no
  submission exists, no score exists.

---

## 1. Frozen package identity

Every competitor receives the byte-identical package below. Any submission must
quote these hashes; a mismatch invalidates the submission.

| File | SHA-256 |
| --- | --- |
| `FROZEN_BRIEF.md` | `dfc37dbc5198af74eb8838a7047618549e0cc544b2db68222222111c28922471` (amendment `A-1`; supersedes pre-amendment `9a3392cd…`, which no competitor ever received) |
| `RED_TEAM_TEST_PLAN.md` | `456b774f4bffc2fbe2f31d13a1e08cef118fff6fd5c2b77a0225019c50c0714d` |
| `seed/README.md` | `b0c0c0aa0957ffa287a5ebdb75b286cc13f5ffcadc22aea46c11f8271c355930` |
| `seed/conflicts.json` | `803b91f39be913b2a6cf010dbbe6fda19e27acbe032bf2a041a17a4794e1bd0f` |
| `seed/projects.json` | `b2306c9762fc138b9e05391f50c5932ec9ed2d1e3726c35fd5f68cb8cb61b80e` |
| `seed/wells.json` | `fd145d758a348831644f7dea5c959432fb7b84751a054c98f12e1dee9a93f4bb` |

Location of the read-only common source package: `/home/user/tournament-common/`

Enforcement, stated precisely:

- `chmod -R a-w` is applied, **and** the ext4 immutable attribute is set
  (`chattr -R +i`). Verified: `touch` returns
  `Operation not permitted` even as root.
- This is a genuine kernel-level block, but a root actor can still run
  `chattr -i` first. The durable control is therefore **detection**: the hash
  table above is the authority, and it lives on the director branch, outside
  the package it describes. Any divergence is provable.

## 2. Proposed roster

| Entry ID | Stance | Branch | Worktree | Launched |
| --- | --- | --- | --- | --- |
| `ENTRY-A` | Reliability-and-security-first | `tournament/entry-a-reliability-security` | `/home/user/tournament-workspaces/entry-a` | **NO** |
| `ENTRY-B` | Mobile-product-and-operator-experience-first | `tournament/entry-b-mobile-operator` | `/home/user/tournament-workspaces/entry-b` | **NO** |
| `ENTRY-C` | Data-intelligence-and-property-graph-first | `tournament/entry-c-data-intelligence` | `/home/user/tournament-workspaces/entry-c` | **NO** |
| `ENTRY-D` (optional) | Deliberately unconventional | `tournament/entry-d-unconventional` | `/home/user/tournament-workspaces/entry-d` | **NO** |

All four branches are forked from the baseline commit
`582d95161cf8220fb37f5224e21e57dcc5c3121c`, **not** from the director branch, so
no workspace contains `tournament/`. Verified empirically — see §3.

No competitor branch has been pushed to `origin`, and none will be pushed
without Ryan's explicit instruction.

## 3. Isolation verification (executed, not asserted)

```
$ git worktree list
/home/user/DataBoss                       582d951 [claude/databossx-tournament-director-ot7k5d]
/home/user/tournament-workspaces/entry-a  582d951 [tournament/entry-a-reliability-security]
/home/user/tournament-workspaces/entry-b  582d951 [tournament/entry-b-mobile-operator]
/home/user/tournament-workspaces/entry-c  582d951 [tournament/entry-c-data-intelligence]
/home/user/tournament-workspaces/entry-d  582d951 [tournament/entry-d-unconventional]
```

Cross-contamination probe — wrote `ISOLATION_PROBE.txt` into `entry-a`:

| Check | Result |
| --- | --- |
| Visible in `entry-a` | yes (expected) |
| Visible in `entry-b` | **no** |
| Visible in the director tree | **no** |
| `tournament/` visible from `entry-a` | **no** |
| `entry-b` `git status` after the probe | clean |

Probe removed afterwards. Each worktree has its own HEAD, index, and working
tree; git itself refuses to check the same branch out twice.

### What this isolation does and does not cover

- **Covered:** branch, working tree, git index, output directory, and control
  artifacts. A competitor cannot read another's work or the rubric internals
  through the filesystem or through git.
- **Not covered:** all four workspaces share one container, one filesystem, one
  network policy, and one set of environment variables. There is no per-entry
  sandbox, no separate user account, and no resource quota. A deliberately
  hostile process could reach another workspace by absolute path.
- **Not covered:** database and deployment isolation are moot right now because
  no prototype exists. Before Phase 2 each finalist must be assigned its own
  SQLite file path and its own port, recorded in its prototype receipt.

This is stated plainly rather than overclaimed. It is adequate for cooperative
competitors following the frozen brief; it is not a security boundary against a
malicious one.

## 4. Neutrality problem — requires Ryan's decision before launch

The director rules require that no model instance be both competitor and sole
judge of its own work, and that the director not favour its own architecture.
Two facts make this a live problem rather than a formality:

**(a) A prior Opus entry already exists.** Open draft PR #58
(`claude/databossx-architecture-design-4b3f4g`) contains
`docs/architecture/DATABOSSX_TOURNAMENT_DESIGN_OPUS.md` — a 1,459-line
architecture tournament response authored by a previous Claude/Opus run on
2026-07-20. A tournament has therefore already been partially run, and an Opus
entry is in it. The current director is also Opus.

**(b) Every competitor available in this session is the same model family.**
This environment can spawn independent runs with different role prompts, but it
cannot run Codex or Cursor. Calling four Opus runs "independent competitors" and
then having an Opus director score them is weak independence, and pretending
otherwise would corrupt the result.

### Options (Ryan chooses; the director will not choose for him)

| # | Option | Effect |
| --- | --- | --- |
| 1 | **Run in-session, disclosed** — four differently-prompted runs, scored by this director, with the weak-independence limitation stamped on every score | Fastest. Results are useful for *design comparison*, not for declaring an objective winner. |
| 2 | **External competitors** — Ryan runs Codex and/or Cursor against the identical frozen package and hands back submissions; this director scores all entries blind by entry ID | Genuine model diversity. Requires Ryan's involvement and time. |
| 3 | **Split judging** — entries produced here, scored by a separate judging run that never sees which entry came from which prompt, with the director only adjudicating disputes | Reduces self-favouring. Still one model family. |
| 4 | **Admit PR #58 as a registered prior entry** (`ENTRY-P58`), scored under the same rubric | Uses work already done. Its author is the same family as the director — must be scored blind. |

The director's recommendation, stated as a recommendation and not a decision:
**Option 2 combined with Option 4**, falling back to **Option 1 + 3** if Ryan
does not want to run external tools. Option 1 alone is acceptable only if every
artifact carries the independence caveat.

## 5. Launch preconditions

No competitor starts until all of the following are true:

1. Ryan selects a roster option from §4.
2. Ryan acknowledges the blockers in the Phase 0 report (`B-1` … `B-4`).
3. Each entry is confirmed to be a separate writer on its own branch.
4. Submission deadline and sealing procedure are set.

## 6. Submission and sealing procedure

1. A competitor writes only inside its own worktree, only to
   `ARCHITECTURE_SUBMISSION.md` during Phase 1.
2. At the deadline the director copies each submission into
   `tournament/submissions/<ENTRY-ID>/`, records its SHA-256, and commits it on
   the director branch.
3. Only then may any entry see another's work.
4. Blind scoring: submissions are re-labelled by entry ID with stance and
   authorship stripped before the rubric is applied.
