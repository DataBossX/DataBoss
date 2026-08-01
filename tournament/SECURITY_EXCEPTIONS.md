# SECURITY EXCEPTIONS

- Register ID: `DBX-SECURITY-EXCEPTIONS-2026-08-01`
- Status: baseline entries recorded at Phase 0. No exception has been *granted*.

An entry in this register is a **known, accepted-or-escalated gap**, not a
waiver. Nothing here permits a competitor to do anything the frozen brief
forbids.

---

## SX-1 — Baseline test suite cannot be run canonically

| Field | Value |
| --- | --- |
| Severity | HIGH (verification integrity) |
| Cause | Session egress policy returns 403 for `pypi.org` and `registry.npmjs.org`. `pytest`, `pydantic`, `openpyxl`, `lxml` are uninstallable. |
| Effect | `python -m pytest -q` cannot run. 11 of 17 test modules cannot import — including every workbook-integrity, repair, validation, and controlled-loop test. |
| Mitigation | A declared stdlib substitute harness produced a partial signal (61 pass / 1 fail / 11 blocked). Every use of that number is labelled harness-derived. |
| Not mitigated | The safety-critical test surface remains unverified in this environment. |
| Escalation | Blocker `B-1` to Ryan. |
| Accepted by | *nobody yet* |

## SX-2 — Holds are not machine-enforced anywhere in the repository

| Field | Value |
| --- | --- |
| Severity | HIGH |
| Cause | No hold registry, hold check, or hold test exists at `582d951`. Grep for `Penterra`, `Section 20`, `Section 17`, `release_hold`, `NO EXTERNAL RELEASE` returns nothing. |
| Effect | The Section 32 / 20 / 17 holds are operational controls only. Nothing in CI would detect an attempt to release held work. |
| Mitigation | Promoted to mandatory prototype capability `P-21` and red-team test `RT-20`; the seed package encodes holds that automation must not be able to clear. |
| Not mitigated | The *live* gap in the real system is unchanged by the tournament. |
| Escalation | Blocker `B-2` to Ryan. |
| Accepted by | *nobody yet* |

## SX-3 — Client identifier present in the public repository

| Field | Value |
| --- | --- |
| Severity | MEDIUM-HIGH (publication policy) |
| Cause | Pre-existing. `horizon/CONTROLLED_LOOP.md` contains project id `DBX-OK-BECKHAM-32-11N-25W`, work-order path `projects/OK-BECKHAM-32-11N-25W/work_orders/WO-SECTION32-QA-001.json`, and private paths of the form `D:/DataBossX/beckham32/final_delivery/...`. |
| Policy | `docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md` classifies real project manifests and private paths as **Internal**. `.gitignore` already blocks `projects/OK-*/`, so the intent is clear and the doc contradicts it. |
| Existing remedy | Open draft **PR #59 — "security: sanitize public workbook QA example"**, unmerged. |
| Director action | **Recorded, not fixed.** Phase 0 forbids code changes, and removing it from the current tree does not erase git history, forks, or caches — that is a coordinated decision belonging to Ryan, per `SECURITY.md`. |
| Escalation | Blocker `B-4` to Ryan. |
| Accepted by | *nobody yet* |

## SX-4 — Competitor isolation is cooperative, not adversarial

| Field | Value |
| --- | --- |
| Severity | MEDIUM |
| Cause | All workspaces share one container, filesystem, network policy, and environment. No per-entry user, sandbox, or quota. |
| Effect | Isolation holds against accident and against normal git operation; a deliberately hostile process could reach another workspace by absolute path. |
| Mitigation | Separate worktrees and branches; competitor branches forked from baseline so `tournament/` is invisible to them; verified by probe; hash table for the common package stored outside it. |
| Escalation | Blocker `B-3` context. Prototype-phase database/port assignment still required. |
| Accepted by | *nobody yet* |

## SX-5 — Prior Opus entry and single-model-family field

| Field | Value |
| --- | --- |
| Severity | MEDIUM (result validity, not safety) |
| Cause | PR #58 contains a prior Opus architecture entry; the director is Opus; every competitor available in-session is the same model family. |
| Effect | "Independent competitors judged by a neutral director" would be an overstatement. |
| Mitigation | Disclosed in `TOURNAMENT_MANIFEST.md` §6 and `COMPETITOR_REGISTRY.md` §4, with four roster options for Ryan to choose from. Blind scoring by entry ID regardless of option. |
| Escalation | Roster decision required before launch. |
| Accepted by | *nobody yet* |

## SX-6 — Private-side writer state is unobservable

| Field | Value |
| --- | --- |
| Severity | MEDIUM |
| Cause | The real corpus and the real work live on a private Windows machine this environment cannot see. |
| Effect | "No active writer lease or conflicting agent" is proven for this repository only. It is **unverified** for the private side. |
| Mitigation | Nothing the tournament does touches the private side; all prototype data is synthetic. |
| Escalation | Blocker `B-3` to Ryan. |
| Accepted by | *nobody yet* |
