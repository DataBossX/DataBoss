# DataBossX Repository Portfolio Disposition

**Generated:** 2026-07-22  
**Scope:** GitHub repositories visible to the connected `rodneydanger84` and `DataBossX` installations  
**Status:** Governance draft only; no archive, delete, transfer, visibility, default-branch, deployment, or merge action is authorized by this document.

## Controlling rules

1. The private Windows truth gate controls production-path decisions. `C:\DataBoss\DataBossX` is the current local canonical candidate; every neighboring local tree remains donor-only until exact reconciliation proves otherwise.
2. `DataBossX/DataBoss` is the public release-train and synthetic-code review surface. It is not authority for private runtime state, client evidence, title conclusions, credentials, or release acceptance.
3. Never wholesale-merge a donor repository into the release train. Port only bounded, reviewed slices with provenance, tests, rollback, and private truth-gate evidence.
4. Verify deployment dependencies before archiving, renaming, transferring, changing visibility, or changing a default branch.
5. Public repositories may contain only code, policy, documentation, and synthetic fixtures. Client names, legal descriptions, source evidence, workbooks, live databases, secrets, private hashes, cloud object identifiers, and release receipts stay private.
6. Vendor forks and generated prototypes must never become accidental sources of truth.

## Repository dispositions

| Repository | Observed role | Disposition | Required proof before any broader action |
|---|---|---|---|
| `DataBossX/DataBoss` | Public DataBossX code and release-train surface | **CANONICAL_PUBLIC_REVIEW_LANE** | Keep draft-gated; private Windows truth, security, recovery, canary, and human-release gates |
| `rodneydanger84/DataBossX` | Large private legacy/control-plane tree on `clean-pr0` | **DONOR_ONLY / PRESERVE** | Local hash reconciliation and bounded component-level diff; never wholesale merge |
| `rodneydanger84/databossx-site` | Full Astro/Tailwind website source candidate with build and site-QA scripts | **DEPLOYMENT_AUTHORITY_CANDIDATE** | Verify current hosting/deployment linkage, domain source, environment, and latest successful deployment |
| `DataBossX/databossx-site` | Much smaller organization website copy | **MIRROR_OR_ARCHIVE_CANDIDATE** | Compare commits and deployment linkage against the personal website repo before any archive/transfer |
| `rodneydanger84/AI-Agent-Control` | Private multi-LLM, title-report, and agent-control experiments | **SELECTIVE_COMPONENT_DONOR** | Source/provenance review, security review, tests, and compatibility with the canonical control kernel |
| `rodneydanger84/sb1-rkcrg9ry` | Browser-side mineral-rights parser using PDF/OCR/Transformers/XLSX tooling | **SELECTIVE_COMPONENT_DONOR** | Deterministic parser tests, resource limits, OCR/model provenance, spreadsheet safety, and evidence controls |
| `rodneydanger84/data-insight-explorer-x` | Lovable/Vite/React analytics prototype | **PROTOTYPE_HOLD** | Named product owner, real specification, deployment evidence, data model, tests, and security review |
| `DataBossX/datahub-prime` | Public Lovable/Vite scaffold with placeholder project metadata | **PUBLIC_PROTOTYPE_CONTAINMENT** | Confirm no active deployment or external dependency; then private/archive or rebuild under an approved product spec |
| `DataBossX/landboss-ops-hub` | Private Lovable/Vite operations prototype closely related to `datahub-prime` | **PROTOTYPE_HOLD / COMPARE** | Exact diff, product owner, deployment evidence, and decision on a single surviving prototype |
| `DataBossX/LandTitleAI` | One-commit “Coming soon” namespace scaffold with a generated default branch | **ARCHIVE_CANDIDATE / NAMESPACE_RESERVE** | Confirm no deployment, package, automation, or external reference depends on it |
| `DataBossX/demo-repository` | GitHub organization demo scaffold | **ARCHIVE_CANDIDATE** | Confirm it is not used for onboarding, Actions tests, or organization demonstrations |
| `rodneydanger84/newdata` | Bolt.new upstream-derived development-tool repository | **VENDOR_FORK / ISOLATE** | Confirm intentional fork/upstream strategy; otherwise archive after dependency check |
| `rodneydanger84/mcp-server-cloudflare` | Cloudflare MCP upstream mirror/fork | **VENDOR_FORK / ISOLATE** | Confirm intentional upstream tracking and local modifications; never mix vendor history into the release train |
| `rodneydanger84/rodneydanger84.github.io` | Legacy static “Lena OS” concept page | **LEGACY_SITE_ARCHIVE_CANDIDATE** | Verify GitHub Pages/domain status and inbound links before archiving |
| `rodneydanger84/Rodney-s-Repository` | Empty private shell | **ARCHIVE_CANDIDATE** | Confirm no external automation references the repository name or ID |
| `rodneydanger84/DataBossXV2` | Empty private shell | **ARCHIVE_CANDIDATE** | Confirm no external automation references the repository name or ID |
| `rodneydanger84/DataBossX.com` | Empty private shell | **ARCHIVE_CANDIDATE** | Confirm no domain, deployment, webhook, or automation references the repository name or ID |

## Immediate operating decision

- Develop no new platform architecture outside `DataBossX/DataBoss` until the private Windows truth gate identifies one bounded implementation slice.
- Keep PR #52 as the primary functional candidate, PR #54 additive, PR #35 donor-only, PR #57 governance-only, and PR #59 as a separate publication-security fix.
- Do not archive or delete repositories during the current HOLD. First produce a deployment/dependency inventory and an owner-approved archive batch.
- Treat the website source, vendor forks, component donors, and prototypes as separate operational classes. Similar names do not establish equivalence.

## Smallest safe next repository action

Run a read-only dependency and deployment provenance pass that answers, for every archive/mirror candidate:

- current default branch and protected-branch state;
- open pull requests and Actions dependencies;
- GitHub Pages, hosting, domain, webhook, package, or deployment linkage;
- inbound references from the canonical repo and local launchers;
- last meaningful commit and unique code not present elsewhere;
- exact recommended action: preserve, mirror, transfer, archive, or bounded port.

No mutation follows automatically from that pass.
