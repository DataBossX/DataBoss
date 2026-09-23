# Repository security baseline

Status: `BLOCKED_WITH_EXACT_GAPS`

Public-safe code can scan clean while the human-only gaps remain:

1. Rotate every credential listed in [SECURITY.md](../../SECURITY.md) and [Issue #2](https://github.com/DataBossX/DataBoss/issues/2).
2. Confirm GitHub secret scanning, push protection, and branch protection ([Issue #72](https://github.com/DataBossX/DataBoss/issues/72)).
3. Keep the [Issue #93](https://github.com/DataBossX/DataBoss/issues/93) publication hold until client-shaped PRs are classified.
4. Do not treat CI green as release authority.

This document records the gap. It is not a rotation receipt and contains no secrets.
