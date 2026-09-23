# Repository security baseline

Outcome: `REPOSITORY_SECURITY_BASELINE_BLOCKED_WITH_EXACT_GAPS`

This note records what the public tree can prove. It does not claim GitHub
organization settings, credential rotation, or a completed secret-incident
closure. Issue #2 remains a veto until the owner rotates keys through each
provider.

## Proven in the current tree

- Secret scan workflow runs Gitleaks on the current tree and PR ranges with
  `contents: read` only.
- Pre-commit includes Gitleaks, private-key detection, and large-file checks.
- Python CI uses `contents: read`.
- Publication-policy tests reject obvious live-key markers and require
  synthetic example manifests.
- Legacy backend data routes are fail-closed without `DATABOSSX_API_TOKEN`.
- Drive connector writes are denied by policy.

## Exact gaps an agent cannot close here

- Branch protection / ruleset evidence for `main`.
- Required independent review and conversation-resolution settings.
- Push protection and secret scanning enablement on the GitHub org.
- CodeQL publication or documented entitlement blocker.
- Dependabot alert state.
- Proof that every historical secret is revoked at the provider.
- Classification and closure of remaining client-shaped public PRs.

Do not treat a green pytest run as `REPOSITORY_SECURITY_BASELINE_PROVEN`.
