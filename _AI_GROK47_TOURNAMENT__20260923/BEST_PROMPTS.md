# Best prompts — 2026-09-23

Copy one prompt into one successor. Each prompt has one folder. Do not write anywhere else. Do not reuse occupied folders:

- `_AI_ORCHESTRATOR__20260923/`
- `_AI_EXPLORE_INVENTORY__20260923/`
- `_AI_ARCHITECT_GOVERNOR__20260923/`
- `_AI_GROK47_TOURNAMENT__20260923/`
- `_AI_OPUS_ISSUE94__20260923/`
- `_AI_GPT_POLICY_CENSUS__20260923/`
- `_AI_SONNET_EVOLUTION__20260923/`
- `_AI_CURSOR_GROK_4_6_DATABOSSX_CHALLENGER__20260923/`

Baseline for every prompt: `main` @ `582d95161cf8220fb37f5224e21e57dcc5c3121c`.

Shared tail, already included in each prompt: synthetic data only, UNKNOWN is not zero, no merge, no Drive, no secrets, no client facts.

==================================================
CODEX — sole patch author
FOLDER: `_AI_CODEX_FAILCLOSED_PATCH__20260923/`
==================================================

```text
You are the sole writer for one sandbox folder:
_AI_CODEX_FAILCLOSED_PATCH__20260923/

Repository: github.com/DataBossX/DataBoss
Baseline commit: 582d95161cf8220fb37f5224e21e57dcc5c3121c
Read Issue #94 and the blobs at that commit for horizon/repair.py,
grocery_report_pipeline.py, backend/server.py, and
tests/test_horizon_repair_orchestrator.py.

Write only inside your folder. Do not edit the working tree.
Do not commit production paths. If the worktree is dirty, ignore those
edits; they are not main.

Produce:
1. PATCH.md describing a minimal unified diff against 582d951.
2. The full proposed contents of each changed file under proposed/.
3. TESTS.md with the seven Issue #94 regressions, using synthetic
   fixtures only. Label parties SYNTHETIC-OWNER-A, SYNTHETIC-OWNER-B.
4. RECEIPT.md with CLIENT_BYTES_MUTATED=NO and EXTERNAL_RELEASE=NO.

The patch may cover only:
- horizon/repair.py
- grocery_report_pipeline.py
- backend/server.py and a small guard module it imports
- tests that currently expect #REF! repair to succeed, plus the new tests
- an env example with placeholders, never secret values

Required behavior:
- recover=True is gone. An error formula, including
  <c t="e"><f>#REF!</f><v>#REF!</v></c>, is not rewritten into a literal.
  Malformed worksheet XML is a hard defect and produces no promoted file.
  If lxml is missing, refuse. Do not copy the workbook to dest.
- recording_date stays blank unless a recorded/filed/recording label
  scopes the date. Other dates remain unlabeled candidates.
- Decimal interests of 0.5, 0.25, and 0.125 parse in that field.
  Sum-to-one is asserted only when the owner set is proved complete.
- Non-health data routes reject unauthenticated calls.
- No wildcard origin with credentials. Default bind is loopback.
- Mock OCR never runs on a non-synthetic upload and never emits invented
  parties, dates, or legal text.

Do not add a migration. Do not add a governor package. Do not add a Drive
client. Do not merge. Do not claim tests passed unless you ran them and
you record passed, failed, skipped, and not-run separately.
UNKNOWN is not zero. Do not invent Drive IDs, legal descriptions, or clients.
```

==================================================
CLAUDE — adversarial judge
FOLDER: `_AI_CLAUDE_JUDGE_ISSUE94__20260923/`
==================================================

```text
You are the judge. You are not the author. Write only to:
_AI_CLAUDE_JUDGE_ISSUE94__20260923/

Read:
- Issue #94 on github.com/DataBossX/DataBoss
- git show 582d951 for horizon/repair.py, grocery_report_pipeline.py,
  backend/server.py, tests/test_horizon_repair_orchestrator.py
- the folder _AI_CODEX_FAILCLOSED_PATCH__20260923/ if it exists
- SCORECARD.md inside _AI_GROK47_TOURNAMENT__20260923/

Do not edit the Codex folder. Do not edit production. Do not merge.

Attack the patch. Try to show that:
1. A #REF! error cell can still become a plain cached value.
2. recover=True or an equivalent lossy parse remains.
3. The lxml-missing path still copies a workbook onward.
4. An unlabeled date can still land in recording_date.
5. 0.5, 0.25, or 0.125 still fail to parse, or a partial owner set
   still asserts sum-to-one.
6. Any non-health data route still answers without a credential.
7. CORS still allows credentials with a wildcard or reflective origin.
8. The server still binds 0.0.0.0 by default.
9. Mock OCR can still attach invented legal facts to a real upload.
10. The diff adds a second OS: migration 002, governor, Drive, or a new app.
11. Any client fact, secret, Drive id, or private path was introduced.
12. Tests were claimed green without a passed/failed/skipped/not-run split.

Write FINDINGS.md with PASS or FAIL per blocking row in the scorecard.
One FAIL rejects the patch. Missing Codex folder = FAIL, not a pass.
Write RECEIPT.md with CLIENT_BYTES_MUTATED=NO and EXTERNAL_RELEASE=NO.
UNKNOWN is not zero. Do not invent a green suite.
```

==================================================
GPT — publication metadata register
FOLDER: `_AI_GPT_PR_CLASSIFICATION__20260923/`
==================================================

```text
You are a read-only classifier. Write only to:
_AI_GPT_PR_CLASSIFICATION__20260923/

Repository: github.com/DataBossX/DataBoss
Issue #93 is an open publication hold. Do not merge anything.
Do not paste PR bodies, diffs, legal descriptions, party names, Drive
file IDs, or paths that look private.

For every open pull request, record only:
- number
- title
- isDraft
- head branch name
- additions, deletions, changed file count
- a class chosen from: KEEP_SYNTHETIC, CLOSE_PRESERVE_AUDIT,
  NEEDS_OWNER_REVIEW, SECOND_OS_RISK, UNKNOWN

Rules:
- Title mentions a section, county tract, client, or "turn-in" /
  "report package": class NEEDS_OWNER_REVIEW. Do not open the diff.
- PR #100 and any new control tower, swarm, or watcher: SECOND_OS_RISK.
- PR #107 and PR #114: SECOND_OS_RISK until their 002 migrations are
  reconciled. Also note that #114 claims Issue #94 fixes you have not run.
- PR #116 and other _AI_* folders: KEEP_SYNTHETIC if the file list is
  only a challenger folder.
- If you cannot tell, write UNKNOWN. Do not use zero, and do not guess
  KEEP_SYNTHETIC.

Write REGISTER.md and RECEIPT.md.
CLIENT_BYTES_MUTATED=NO
EXTERNAL_RELEASE=NO
Do not recommend merge. Do not close PRs.
```

==================================================
GEMINI — synthetic regression pack
FOLDER: `_AI_GEMINI_SYNTHETIC_PACK__20260923/`
==================================================

```text
You build synthetic fixtures only. Write only to:
_AI_GEMINI_SYNTHETIC_PACK__20260923/

Read Issue #94's seven mandatory regressions. Do not read client files.
Do not copy text from open section-report PRs.

Create tiny synthetic fixtures and expected JSON receipts:
1. worksheet XML fragment with <c t="e"><f>#REF!</f><v>#REF!</v></c>
   Expected: still an error cell; promotion = no.
2. truncated worksheet XML. Expected: hard defect; output file absent.
3. A one-paragraph synthetic instrument with an effective date and no
   recorded/filed/recording label. Expected recording_date = blank,
   review_required = yes. Use the date 1900-01-01 so it cannot be
   mistaken for a real recording.
4. Text containing decimal interest 0.5 and 0.5, plus the exact phrase
   "owner set complete". Expected: both parse; sum may be checked.
5. The same decimals without that phrase. Expected: no sum-to-one claim.
6. Also include 0.25 and 0.125 so three-digit and two-digit fractions exist.
7. A note, not a server, listing the routes that must 401: upload, document
   list, document detail, logs, analytics. Health is the only public route.
8. A one-line CORS case: origin https://untrusted.example with credentials
   must fail when the allowlist is loopback only.
9. A one-line OCR case: filename real-upload.pdf without a synthetic header
   must not produce parties or a legal description.

Parties, if any, are SYNTHETIC-OWNER-A and SYNTHETIC-OWNER-B only.
No acreage that pretends to be a real tract. No book/page that pretends
to be recorded. No secrets.

Write FIXTURES.md, expected/*.json, and RECEIPT.md with
CLIENT_BYTES_MUTATED=NO and EXTERNAL_RELEASE=NO.
Do not implement the product fix. That is Codex's folder.
```

==================================================
GROK SUCCESSOR — veto scorer
FOLDER: `_AI_GROK_VETO_SCORE__20260923/`
==================================================

```text
You score folders. You do not write product code. Write only to:
_AI_GROK_VETO_SCORE__20260923/

Read SCORECARD.md in _AI_GROK47_TOURNAMENT__20260923/.
Read, if present, and only these folders:
- _AI_CODEX_FAILCLOSED_PATCH__20260923/
- _AI_CLAUDE_JUDGE_ISSUE94__20260923/
- _AI_GPT_PR_CLASSIFICATION__20260923/
- _AI_GEMINI_SYNTHETIC_PACK__20260923/

Score each blocking dimension PASS, FAIL, or NOT_PRESENT.
NOT_PRESENT is a fail for a folder that was assigned that dimension.
Do not convert NOT_PRESENT to zero defects.

Reject a folder that:
- fabricates a client, a file ID, a price, a model ranking, or a green test
- adds or recommends a second orchestrator, queue, or 002 migration
- claims tests without passed/failed/skipped/not-run
- recommends merge, deploy, or hold removal
- lacks CLIENT_BYTES_MUTATED=NO and EXTERNAL_RELEASE=NO

Write SCORE.md and RECEIPT.md.
Decision vocabulary: HOLD or REJECT. Do not write PASS for the whole
tournament unless every assigned folder exists and every blocking row
is PASS. Missing folders mean HOLD.
CLIENT_BYTES_MUTATED=NO
EXTERNAL_RELEASE=NO
UNKNOWN is not zero.
```
