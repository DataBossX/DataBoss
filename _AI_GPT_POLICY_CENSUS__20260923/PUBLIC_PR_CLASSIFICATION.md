# Open public PR classification

Snapshot: 2026-09-23T19:46:14Z.

This is conservative publication triage, not merge authorization. It uses PR
numbers only. `KEEP_SYNTHETIC` means retain for independent public-safety
review; it does not mean merge. `CLOSE_PRESERVE_AUDIT` means close unmerged
while retaining a sanitized audit record; closure does not erase public
history. `OWNER_REVIEW` means the available evidence is insufficient for an
automatic keep/close decision.

| PR | Classification | Basis |
|---:|---|---|
| #32 | KEEP_SYNTHETIC | Narrow publication-gate candidate; independent review still required. |
| #59 | KEEP_SYNTHETIC | Narrow sanitization candidate; independent review still required. |
| #95 | CLOSE_PRESERVE_AUDIT | Contains deliverable-shaped and release-shaped artifacts. |
| #96 | OWNER_REVIEW | Mixed synthetic UI and production-path changes. |
| #97 | CLOSE_PRESERVE_AUDIT | Adds external-sync and report-production paths. |
| #98 | CLOSE_PRESERVE_AUDIT | Contains report, source-census, and receipt artifacts. |
| #99 | OWNER_REVIEW | Generic-looking code requires content and lineage review. |
| #100 | CLOSE_PRESERVE_AUDIT | Large control/receipt lineage is internal by policy. |
| #101 | CLOSE_PRESERVE_AUDIT | Contains completed deliverable-shaped files. |
| #102 | CLOSE_PRESERVE_AUDIT | Report repair and findings material is internal by policy. |
| #103 | OWNER_REVIEW | Broad validation code requires public-safety review. |
| #104 | CLOSE_PRESERVE_AUDIT | Contains project-specific findings and receipt-shaped artifacts. |
| #105 | CLOSE_PRESERVE_AUDIT | Includes verified inventory data and audit artifacts. |
| #106 | CLOSE_PRESERVE_AUDIT | Receipt-only operational artifact is internal by policy. |
| #107 | OWNER_REVIEW | Generic engine code requires security and overlap review. |
| #108 | OWNER_REVIEW | Mixed receipt and code change requires owner review. |
| #109 | OWNER_REVIEW | Generic dashboard code lacks sufficient publication proof. |
| #110 | CLOSE_PRESERVE_AUDIT | Finish/package lineage includes operational receipts. |
| #111 | CLOSE_PRESERVE_AUDIT | Large report-production lineage exceeds public-safe scope. |
| #112 | CLOSE_PRESERVE_AUDIT | Package documentation is project/report specific. |
| #113 | CLOSE_PRESERVE_AUDIT | Package builder and documentation are project specific. |
| #114 | OWNER_REVIEW | Broad kernel, connector, and sync change requires owner review. |
| #115 | CLOSE_PRESERVE_AUDIT | Project-specific successor/package material. |
| #116 | CLOSE_PRESERVE_AUDIT | Agent tournament artifacts are internal operating records. |
| #117 | OWNER_REVIEW | Broad mixed security, runtime, governance, and artifact change. |

## Totals

- `KEEP_SYNTHETIC`: 2
- `CLOSE_PRESERVE_AUDIT`: 15
- `OWNER_REVIEW`: 8
- Total open public PRs: 25

No classification proves that historical content, branches, forks, caches, or
credentials are clean. Those states remain `UNKNOWN` absent separate evidence.
