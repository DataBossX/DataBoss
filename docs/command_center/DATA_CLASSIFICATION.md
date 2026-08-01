# DATA CLASSIFICATION — DataBossX Command Center

Release state: **FOR REVIEW — HOLD — NO EXTERNAL RELEASE**

## Classes

| Class | Definition | May reach cloud control plane? | May reach phone? | May reach public repo? |
| --- | --- | --- | --- | --- |
| **C0 — Public** | Marketing copy, open-source code, published law | Yes | Yes | Yes |
| **C1 — Internal** | Architecture docs, policy versions, synthetic fixtures | Yes | Yes | Yes |
| **C2 — Operational** | Command/job/lease/approval IDs, hashes, receipts, audit events | Yes | Yes (redacted) | Metadata only |
| **C3 — Client-identifying** | Client names, project names, legal descriptions, cloud IDs, absolute paths | **Pseudonymized only** | Pseudonymized only | **Never** |
| **C4 — Raw evidence** | Deeds, abstracts, workbooks, scans, extracted text | **Never** | **Never** (references only) | **Never** |
| **C5 — Secrets** | Credentials, tokens, keys, session material | **Never** in content | **Never** | **Never** |

## Rules enforced in code

1. **C4 never leaves the local boundary.** The runner posts metadata and
   receipts only; artifact bytes stay in its working directory.
2. **C5 is never returned by any route.** There is no secret-status endpoint —
   even confirming a key *exists* is refused (`secrets.probe_status` is a
   prohibited operation).
3. **Absolute paths are C3 and are redacted**, not masked in place, by
   `voice.redact_for_phone` before any response leaves the process. Removed
   keys: `canonical_folder`, `root_path`, `local_path`, `absolute_path`,
   `secret`, `api_key`, `token`, `password`, `credential`. Windows drive
   letters, UNC paths, and `/home|/root|/Users|/mnt|/var` paths become
   `[redacted-path]`.
4. **Everything in this lane is synthetic.** `artifacts.synthetic` defaults to
   1; `NoFabricationWatcher` raises a BLOCKING finding if a non-synthetic
   artifact appears.
5. **Transcripts are C3.** Stored with a hash; **raw audio is discarded** after
   successful transcription (`audio_retained` is always false).
6. **Resource scopes are logical, never paths.** `project.synthetic-alpha`, not
   `C:\DataBoss\...`. Enforced by `validate_scope`.

## Retention

| Data | Retention | Basis |
| --- | --- | --- |
| Raw audio | Discarded immediately after transcription | Minimization |
| Transcript + hash | Life of the command record | Auditability |
| Audit events | Permanent, append-only | Hash chain integrity |
| Receipts | Permanent | Proof of what happened |
| Artifact versions | Permanent; accepted versions immutable | Never overwrite accepted work |
| Runner working directories | Per job; `out/` removed on rollback | Bounded execution |
| Sessions | 1 hour | Limits theft window |

## Existing incident constraints honoured

`SECURITY.md` records that `backend/.env` and client metadata were committed to
the public repository. This lane therefore:

- adds **no** `.env`, credential, or client value anywhere;
- adds **no** real project name, legal description, or cloud ID;
- uses `synthetic-alpha` and `SYNTHETIC OWNER A/B/C` throughout;
- keeps every screenshot on synthetic data — no client fact is rendered.

Verification: `grep` for client markers, drive letters, and secret patterns
across all files added this cycle returns nothing. See the final receipt.
