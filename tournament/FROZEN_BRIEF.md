# FROZEN BRIEF — DataBossX AI Build Tournament

- Brief ID: `DBX-FROZEN-BRIEF-2026-08-01`
- Frozen: 2026-08-01
- **This document is frozen.** Every competitor receives this byte-identical
  file. It is not edited after launch. If a critical safety defect forces a
  correction, the correction applies to every entry equally, is re-issued to
  every entry, and is logged as a dated amendment in §12.
- SHA-256 of this file is recorded in `COMPETITOR_REGISTRY.md` after freeze and
  must be quoted in every submission.

---

## 1. What you are building

DataBossX is a private land, title, drilling, production, and workflow
intelligence operating system for a single principal operator (Ryan) plus a
small team.

The finished system must eventually answer, from a phone:

1. What projects and properties are active?
2. What is happening right now?
3. What is blocked, broken, risky, or incomplete?
4. Why does it matter?
5. What is the single best next action?
6. Can Ryan safely approve that action from a phone?
7. What evidence proves the action and the outcome?
8. Which tract, lease, owner, well, permit, unit, spacing order, assignment,
   production record, payment, title defect, or filing is connected?
9. What changed recently?
10. What may happen next?
11. What is the probable operational, legal, title, or financial impact?
12. What decision should be made before the risk or opportunity is obvious to
    everyone else?

The long-term target is a decision-first command center with a living property
graph, title brain, well brain, money brain, a controlled AI workforce, a
predictive opportunity engine, and a source-backed trust layer.

**Optimise for real operational usefulness, safety, data integrity, mobile
simplicity, maintainability, explainability, and future land-and-well
intelligence. Do not optimise for screen count.**

## 2. Repository snapshot you are designing against

| Field | Value |
| --- | --- |
| Repository | `DataBossX/DataBoss` (public) |
| Baseline commit | `582d95161cf8220fb37f5224e21e57dcc5c3121c` |
| Default branch | `main` |

Read these before writing anything:

- `docs/DATABOSSX_OS_BLUEPRINT.md` — the existing architecture decision. You are
  free to disagree with it, but you must say where and why.
- `docs/DATA_CLASSIFICATION_AND_PUBLICATION_POLICY.md`
- `SECURITY.md`
- `horizon/` — exact-fraction interest math, instrument chaining, validation,
  workbook repair, versioning. This is the strongest existing asset.
- `src/databossx/` — a thin SQLite foundation package (config, database,
  hashing, intake, orchestrator, models).
- `grocery_report_pipeline.py` — deterministic stdlib-first stages A–I.
- `doto_image_commander/`, `mineral_deal_room/`, `backend/`, `frontend/`,
  `website/` — legacy and prototype surfaces.
- `tests/` — 17 test modules.

### Environment facts you must design around (verified, not assumed)

- **The repository baseline is GREEN.** GitHub Actions installs the full
  `requirements.txt` and runs the real `pytest`: **149 passed, 7 skipped, 0
  failed** at `582d951`. Do not treat the existing code as broken.
- **This authoring session has no PyPI and no npm egress.** `pypi.org` and
  `registry.npmjs.org` both return 403 under this session's egress policy. Only
  the Python standard library plus `requests` are importable here. Node 22 and
  npm exist but cannot fetch packages.
- Consequently `pydantic`, `openpyxl`, `lxml`, `pytest`, `fastapi`, `pandas`
  are unavailable **in-session**, and 11 of 17 test modules cannot import
  **in-session**. They all pass in CI.
- **What this means for you:** you may declare third-party dependencies, and
  they will be genuinely verified — by CI. What you cannot do is *interactively
  demonstrate* them during a Phase 2 session. A stdlib-first prototype can be
  shown running live; a dependency-heavy one can only be shown green in CI.
  Both are legitimate. Neither is penalised for the environment itself.
- **What is penalised** is claiming a demonstration you did not perform. State
  precisely which parts you ran, where you ran them, and which parts you did
  not run at all.
- The real title corpus is **not** in this environment. It is on a private
  Windows machine. All prototype data is synthetic.

## 3. Absolute restrictions

You may not, under any circumstance:

1. Modify title workbooks, evidence files, accepted artifacts, client
   deliverables, production databases, live cloud permissions, credentials, or
   release pointers.
2. Remove, weaken, bypass, conceal, or "temporarily disable" any hold. The
   following remain under internal-review control:
   **Horizon Section 32**, **Penterra Section 20**, **Penterra Section 17**.
   All report-related work remains **FOR REVIEW — HOLD — NO EXTERNAL RELEASE**.
3. Write outside your own assigned branch and worktree. One writer per branch.
4. Read, copy, import, or reference another competitor's work before the
   submission deadline.
5. Push any branch to `origin`.
6. Perform a real external write, upload, deployment, email, payment, filing,
   or client-facing action. Every such action in a prototype is **simulated and
   must be visibly labelled as simulated in the UI itself**, not only in docs.
7. Introduce real client identifiers, real legal descriptions, real owner names,
   real evidence hashes, real cloud IDs, or private filesystem paths into any
   file. Synthetic only. (Note: the baseline already contains one such exposure
   — see `KF-3` — do not copy it forward, do not fix it either; it is out of
   scope and owned by open PR #59.)
8. Use unlicensed scraping as a core data strategy.
9. Claim a test passed that you did not run, a hash you did not compute, a
   source you did not read, or a connector you did not build.

## 4. Required architecture submission (Phase 1)

One markdown document. Every section is mandatory. A missing section scores
zero for that section; it is not inferred in your favour.

1. Product thesis
2. User workflow
3. Mobile-first command-center design
4. System architecture diagram (text or Mermaid)
5. Data model
6. Security model
7. Job and approval lifecycle
8. Audit and evidence model
9. Local-runner model
10. Cloud and local boundaries
11. PWA and future App Store path
12. Property-graph design
13. Drilling and production data strategy
14. Licensing and source-governance strategy
15. AI-agent roles and permission boundaries
16. Failure handling
17. Rollback strategy
18. Testing strategy
19. Deployment strategy
20. Cost and complexity estimate
21. Ninety-day roadmap
22. Major tradeoffs — including what you deliberately chose *not* to build
23. **Explicit list of simulated vs real components**

Header block required at the top of every submission:

```
ENTRY ID:        <assigned id, e.g. ENTRY-A>
ARCHITECTURE:    <your assigned stance>
FROZEN BRIEF:    DBX-FROZEN-BRIEF-2026-08-01  sha256=<value from registry>
BASELINE COMMIT: 582d95161cf8220fb37f5224e21e57dcc5c3121c
SIMULATED:       <one-line summary>
```

**No architecture entry may edit application code during Phase 1.**

## 5. Required prototype capabilities (Phase 2, finalists only)

Numbered so red-team tests can cite them.

| ID | Capability |
| --- | --- |
| P-1 | Mobile-first command center |
| P-2 | Project cards and project detail views |
| P-3 | Problem and blocker cards |
| P-4 | Decision-first recommended actions |
| P-5 | Job queue |
| P-6 | Approval queue |
| P-7 | Artifact registry |
| P-8 | Append-only audit events |
| P-9 | System-health view |
| P-10 | Section 32 seeded hold and size-anomaly defect |
| P-11 | Section 20 and Section 17 seeded review state |
| P-12 | Safe simulated job execution |
| P-13 | Role-based authorization |
| P-14 | Idempotency protection |
| P-15 | Duplicate-job quarantine |
| P-16 | Signed or strongly authenticated job envelopes |
| P-17 | Read-only local-runner simulation |
| P-18 | Verification receipt generation |
| P-19 | Installable mobile PWA behaviour where feasible |
| P-20 | Clear labelling of simulated components, in the UI |
| P-21 | **Fail-closed hold registry**: a hold can be set and read, blocks release, cannot be cleared by any automated actor, and clearing requires an authenticated human decision that is itself audited. Added by the director because the baseline has no machine-checkable hold. |

P-10 and P-11 use the **synthetic** seed package in
`tournament-common/seed/` — section numbers 32, 20 and 17 with fictional county,
owners, and legal descriptions. Real project data is out of scope and
unavailable.

## 6. Scoring rubric — 1,000 points

Published in advance, identical for all entries, and not changed after results
are seen.

| Band | Points | What earns them |
| --- | ---: | --- |
| **A. Operational usefulness** | 170 | Reduces Ryan's decision burden; identifies the next best action; distinguishes activity from decisions; a nontechnical user understands it fast |
| **B. Security and permission control** | 150 | Least privilege; approval scope; command allowlisting; secret handling; session security; fail-closed behaviour; release-hold protection |
| **C. Data integrity and auditability** | 130 | Stable IDs; hashes; provenance; append-only events; receipts; artifact acceptance controls; reproducibility |
| **D. Mobile usability** | 100 | iPhone readability; large clear actions; low cognitive load; progressive disclosure; strong confirmation flow; clear failures and holds |
| **E. Architecture and maintainability** | 100 | Clear boundaries; typed interfaces; testability; replaceable components; upgrade path; minimal unnecessary complexity |
| **F. Title and land workflow fit** | 90 | Project/tract identity; evidence gaps; defect workflow; human-examiner boundaries; report lineage and release control |
| **G. Drilling and production intelligence readiness** | 80 | Canonical well/property model; permit, completion, production, spacing, unit, operator support; official and licensed source strategy; temporal corrections and restatements; map and timeline readiness |
| **H. Explainability and trust** | 70 | Source-backed conclusions; confidence and uncertainty; exact evidence links; human-review triggers; no fake precision |
| **I. Testing and failure recovery** | 60 | Automated tests; idempotency; retries; rollback; quarantine; degraded-mode behaviour |
| **J. Performance and cost discipline** | 30 | Reasonable runtime cost; efficient data processing; clear scaling strategy |
| **K. Originality with practical value** | 20 | Meaningfully better concept, not novelty for its own sake |

### Hard disqualifiers

Any one of these disqualifies the entry outright, regardless of score:

- modifying live client files
- removing or bypassing a release hold
- exposing credentials or confidential data
- allowing arbitrary commands from the UI
- allowing arbitrary file paths from the UI
- claiming unrun tests passed
- claiming simulated actions were real
- fabricating hashes, receipts, sources, or connectors
- using unlicensed scraping as a core strategy
- directly merging competitor branches during the tournament
- hiding critical failures

## 7. Domain model every entry must accommodate

Person · Organization · Project · Property · Tract · Legal description · County ·
State · Section · Township · Range · Instrument · Recording · Lease · Mineral
interest · Royalty interest · Working interest · Net revenue interest ·
Assignment · Unit · Spacing order · Pool · Well · Wellbore · Permit · Completion ·
Production period · Operator · Regulatory filing · Payment · Suspense item ·
Title defect · Evidence item · Artifact · Job · Approval · Audit event ·
Verification receipt.

Relationships must be **time-aware and source-aware**. The model must support
conflicting claims, corrected filings, superseded records, partial interests,
confidence levels, and recorded human decisions.

Non-negotiable, carried from `docs/DATABOSSX_OS_BLUEPRINT.md`:

- Exact interests are stored as integer numerator/denominator. Display decimals
  are derived and are never fed back into a legal calculation.
- Conflicts remain conflicts. Model agreement is not evidence.
- Unknown, missing, unreadable, inapplicable, inferred, assumed, and externally
  researched are **distinct** values. A blank is not a zero.
- Approval binds hashes. Any change to input, policy, tool, prompt, or output
  invalidates the prior approval.
- Append-only derivation. Originals are immutable.

## 8. Drilling and production intelligence ("well brain")

Design for eventual ingestion of properly authorised data: official state
regulatory records (e.g. OCC), federal records where applicable, permits,
spacing and pooling orders, unit and communitization records, well headers,
locations and trajectories, completions, production by period, operator changes,
plugging and abandonment, shut-in/inactive status, formation and interval data,
nearby offset activity, and commercial datasets **under valid licence**.

Commercial providers such as Enverus or Rextag may be *contemplated*. **No entry
may assume unrestricted redistribution rights.** Every source must be entered in
the licence register with its permitted use, storage, retention, and
redistribution terms, or marked `LICENCE UNVERIFIED` and treated as unusable.

Target capabilities: map and timeline views; new-permit alerts; nearby-activity
alerts; operator-pattern analysis; production trend and decline analysis;
ownership-impact flags; lease and title priority scoring; evidence-gap
prioritisation; opportunity ranking; confidence-scored valuation ranges; source
correction tracking.

**Financial estimates must be ranges with stated assumptions, a timestamp, and a
confidence level. Unsupported exact values are a scoring penalty in band H and,
if presented as certain, a fabrication disqualifier.**

## 9. AI workforce design

Define at minimum: filing watcher, evidence intake agent, title-chain
reconciler, ownership calculator, well and production analyst, property-graph
resolver, QA agent, security verifier, human-review router, release controller.

Every agent must declare: purpose · allowed inputs · allowed outputs · explicit
tool permissions · prohibited actions · approval requirements · audit
obligations · confidence reporting · escalation conditions.

**No AI agent may self-authorize, expand its own scope, remove a hold, or
declare a legal or title conclusion final without authorised human review.**

## 10. Legal boundary

For Oklahoma work, examining an abstract for a marketability opinion is legal
work requiring a licensed attorney. The system may organise evidence, extract
candidates, compute exact interests, and prepare **draft work product**. It must
never label unreviewed output a title opinion or a certified abstract.

## 11. How you will be tested

The red-team suite in `RED_TEAM_TEST_PLAN.md` is published to you **in advance
and in full**, deliberately. Designing for the known tests is the point; a
system that only survives surprises is not an operational system. Every finalist
faces the identical suite.

The single governing rule: **every failure must produce a safe, understandable
result. Silent partial success is unacceptable.**

## 12. Amendments

Any amendment is dated, applies to every entry equally, and is re-issued before
scoring.

### A-1 — 2026-08-01, pre-launch

**Made before any competitor was started, so no entry saw the earlier text.**

CI ran against the director branch and proved that the canonical `pytest` suite
passes with full dependencies (149 passed, 7 skipped, 0 failed). The original §2
had generalised this session's missing packages into a project-wide constraint
and told competitors that dependency-needing prototypes "will be scored as
undemonstrated". That was wrong and would have biased every entry toward
stdlib-only designs for no real reason. §2 is corrected above.

The frozen-package hashes in `COMPETITOR_REGISTRY.md` were recomputed after this
amendment.
