# Next 100 Best Moves

Status: public-safe backlog for the trusted kernel. This is not a client run,
release, or certification. Items marked **DONE** landed in the current branch.
Items marked **HUMAN** cannot be completed by an agent.

## Done in this branch

1. **DONE** Refuse workbook repair that downgrades an Excel error formula to a cached literal.
2. **DONE** Strict worksheet XML parse; malformed XML is a hard defect with no promotion.
3. **DONE** Never invent `recording_date` from an unlabeled date.
4. **DONE** Keep unlabeled dates as review candidates only.
5. **DONE** Parse ordinary decimal interests (`0.5`, `0.25`, `0.125`).
6. **DONE** Assert sum-to-one only when the owner set is proved complete.
7. **DONE** Authenticate every non-health legacy backend data endpoint.
8. **DONE** Remove credentialed wildcard CORS from the legacy backend.
9. **DONE** Bind the legacy backend to loopback only.
10. **DONE** Disable mock OCR outside explicit demo mode; demo mode emits no legal facts.
11. **DONE** Enforce upload size and type limits.
12. **DONE** Add numbered migration runner (`001` + `002`).
13. **DONE** Persist claims, evidence spans, conflicts, review gates, and connector cursors.
14. **DONE** Add a fail-closed policy engine.
15. **DONE** Add legal task-graph transitions, leases, and idempotent task seeds.
16. **DONE** Add a read-only Google Drive connector with local-mirror and injected API backends.
17. **DONE** Add a Drive/local sync planner that copies into the vault only.
18. **DONE** Refuse Drive writes, deletes, and shares by default.
19. **DONE** Expose kernel health, tasks, audit, claims, and Drive scan on the control API.
20. **DONE** Add `python -m databossx` CLI for health, project create, scan, and vault ingest.
21. **DONE** Port Horizon exact-interest math as the canonical `titlemath` adapter.
22. **DONE** Verify vault copies by re-hashing destination bytes.
23. **DONE** Pin Python CI to 3.11, add `PYTHONPATH=src`, and add `requirements-test.txt`.
24. **DONE** Add publication-policy smoke tests for synthetic examples and secret markers.
25. **DONE** Remove the accidental `backend/=0.7.0` pip log from the tree.
26. **DONE** Add Issue #94 mandatory regression tests.

## Human / security gates

27. **HUMAN** Rotate every credential named in `SECURITY.md` and issue #2.
28. **HUMAN** Decide history rewrite vs. leave-and-contain for past secret commits.
29. **HUMAN** Enable GitHub push protection, secret scanning, and required reviews (issue #72).
30. **HUMAN** Close or classify remaining client-shaped public PRs (issue #93).
31. **HUMAN** Do not merge PR #25 as a second title authority.
32. **HUMAN** Review PR #26 / Title Factory as donor code only after publication screening.
33. **HUMAN** Run inventory-only on the real Windows corpus; do not upload it here.
34. **HUMAN** Qualified examiner review and hash-bound release of one real candidate.

## Trusted kernel

35. Add task dependency wake-up so child tasks become READY only after parents succeed.
36. Persist lease heartbeats from worker processes, not just library helpers.
37. Recover READY from expired leases on API startup.
38. Add outbox publisher that never mutates source bytes.
39. Bind approvals to input manifest + output hash + policy version.
40. Block project status advance when any material conflict is OPEN.
41. Block RELEASED if source bytes changed after EVIDENCE_LOCKED.
42. Add FTS5 search over claims and evidence snippets with citation payloads.
43. Store mime types during inventory instead of empty strings.
44. Reject path traversal, symlinks, and archive bombs at intake.
45. Record worker capability registry in SQLite.
46. Add deterministic OCR worker interface with no provider hardcoding.
47. Add vision worker that is policy-blocked under local-only profile.
48. Add extraction worker that returns candidate envelopes, never direct DB writes.
49. Reject provenance that does not cover the semantic field region.
50. Normalize parties while preserving original strings.
51. Build instrument / lease / assignment / well chain tables from claims.
52. Property-test interest conservation across random valid fractions.
53. Duplicate instruments must not double-count interests.
54. Missing fields stay null and create review work, never inferred known values.
55. Add review-gate records for inventory lock, examiner review, and export.
56. Render a control workbook separately from any client candidate.
57. Compare OOXML parts against the approved template before export.
58. Fail workbook integrity if writes occur outside approved ranges.
59. One writer: orchestrator commits all state transitions.
60. Crash/restart produces equivalent manifests for inventory and hashing.

## Drive and connectors

61. Live Google client using `drive.file` and a stored page token only.
62. Drive change-feed poller that treats notifications as signals, not evidence.
63. GitHub metadata connector with `contents:read` / `metadata:read`.
64. Dropbox app-folder metadata connector.
65. Chat-export connector for reviewed local export zips.
66. Hugging Face metadata connector.
67. Connector least-privilege tests that prove writes are impossible without approval.
68. Incremental scan equivalence tests (second scan is cursor-only).
69. Rate-limit and retry wrappers with circuit breakers.
70. Credential references in `source_connections.credential_ref` only.
71. Never persist tokens, refresh tokens, or file contents in audit payloads.
72. Bounded-root tests: connectors cannot walk above the registered locator.

## Product migration

73. Split grocery stages A–I into typed kernel tasks.
74. Stop original-file quarantine moves; plan-only remains.
75. Migrate DOTO queue onto the common task graph with explicit cost approval.
76. Replace mineral-deal-room sample data with the control API.
77. Retire the CRA frontend after the Vite command center exists.
78. Retire mock backend routes once the control API covers upload/review.
79. One audit stream for Horizon, grocery, DOTO, and deals.
80. Provider-neutral model catalog after deterministic workers are complete.

## Command center and docs

81. Vite/React projects + release status view.
82. Evidence viewer with source-region highlights.
83. Examiner review queue that shows competing claims side by side.
84. Exact-interest ledger UI that never edits fractions as floats.
85. Connector health and inventory coverage panel.
86. Append-only audit timeline with FTS.
87. Policy / approval / settings screens.
88. Replace dated grocery Monday-risk language in operator docs.
89. Keep public README free of client legal descriptions and Drive IDs.
90. Generate operator receipts that omit private paths and hashes.

## Hardening and tests

91. Adversarial tests: prompt injection in a deed cannot change policy.
92. Adversarial tests: zip bombs and traversal paths are contained.
93. Stale approval cannot publish.
94. Stale task lease cannot publish.
95. Secrets do not enter prompts, logs, events, or browser bundles.
96. Golden synthetic corpus for extraction/review — no real client bytes.
97. Pin remaining GitHub Actions to immutable SHAs after verifying digests.
98. Dependabot or equivalent for Python and website lockfiles.
99. CodeQL or documented entitlement blocker (do not fake green).
100. Keep one canonical runtime. Older command centers, swarms, and factories stay donor-only.
