# Credential Rotation Evidence

Names-and-status only. **Never** record, paste, or commit an actual credential
value, fragment, fingerprint, or replacement here or anywhere else.

Removing a value from the current tree does not revoke it. Every credential that
was ever committed to Git history must be revoked and rotated at its provider.
Code and repository changes alone do **not** rotate a credential.

## Status legend

- `BLOCKED_EXTERNAL` — rotation requires action at an external provider console
  and cannot be completed or verified from this repository.
- `ROTATION_VERIFIED` — an authorized human (Rodney) confirmed at the provider
  that the old credential is revoked and a new one is issued. Set only by that
  human, never by an automated change.

## Evidence table

| # | Credential name | Source location (historical) | Rotation status | Verified by | Verified at (UTC) |
|---|-----------------|------------------------------|-----------------|-------------|-------------------|
| 1 | `OPENAI_API_KEY` | `backend/.env` (git history) | `BLOCKED_EXTERNAL` | — | — |
| 2 | `ANTHROPIC_API_KEY` | `backend/.env` (git history) | `BLOCKED_EXTERNAL` | — | — |
| 3 | `CLAUDE_API_KEY` | `backend/.env` (git history) | `BLOCKED_EXTERNAL` | — | — |
| 4 | `GEMINI_API_KEY` | `backend/.env` (git history) | `BLOCKED_EXTERNAL` | — | — |
| 5 | `QWEN_API_KEY` | `backend/.env` (git history) | `BLOCKED_EXTERNAL` | — | — |
| 6 | `GROK_API_KEY` | `backend/.env` (git history) | `BLOCKED_EXTERNAL` | — | — |
| 7 | `GOOGLE_DRIVE_API_KEY` | `backend/.env` (git history) | `BLOCKED_EXTERNAL` | — | — |
| 8 | MongoDB credentials in `MONGO_URL` | `backend/.env` (git history) | `BLOCKED_EXTERNAL` | — | — |

All rows remain `BLOCKED_EXTERNAL` until Rodney verifies rotation directly at
each provider. Do not change a status to `ROTATION_VERIFIED` based on code
review, tree deletion, or CI results.

## Verification procedure (per credential)

1. Rodney authenticates to the provider console.
2. Revoke the exposed credential.
3. Issue a replacement and store it only in an approved secrets manager or a
   local `.env` that is git-ignored.
4. Confirm the old credential no longer authenticates.
5. Update this row's status to `ROTATION_VERIFIED` with initials and UTC time —
   still with **no value** recorded.
