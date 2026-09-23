# DataBossX publication-policy census

This directory is a public-safe, read-only census. It contains no client facts,
no matched scanner values, and no publication authorization.

## Headline result

- Open public pull requests classified: **25**
- Public issues returned by the repository inventory: **17**
- Current-tree conservative publication gate: **FAIL**
- Redacted current-tree findings: **34**
- Specialist gate tests: **9 passed**
- Client bytes mutated: **NO**

`UNKNOWN` is never interpreted as zero. In particular, this census does not
prove credential revocation, history cleanup, branch deletion, or absence from
forks and caches.

## Deliverables

- `PUBLIC_PR_CLASSIFICATION.md` — number-only open-PR triage.
- `publication_policy_gate.py` — dependency-free, read-only scanner.
- `test_publication_policy.py` — synthetic fixtures plus non-enforcing current
  tree census coverage.
- `CENSUS.json` — machine-readable count definitions and results.
- `RECEIPT.md` — mutation receipt.

## Gate behavior

The scanner blocks high-confidence credential forms and credential
assignments, private `D:\` paths, contextual cloud file/folder IDs, and
client-report-shaped filenames. It also fails closed on missing roots,
symlinks, unreadable files, and oversized inputs.

Known public policy files, explicit synthetic-fixture paths, and architecture
documentation are allowlisted only for path/ID/report examples. Credential
rules remain active in those files. Command output contains rule names, line
numbers, and path digests; it does not print matched values or filenames.

Run:

```bash
python3 _AI_GPT_POLICY_CENSUS__20260923/publication_policy_gate.py --json .
python3 -m pytest -q _AI_GPT_POLICY_CENSUS__20260923/test_publication_policy.py
```

The current FAIL is conservative and is not proof that every finding is a live
secret or private client artifact. It means the tree cannot be automatically
approved for publication without remediation or documented human review.
