# CI / GitHub Actions Security Notes

## Current workflows

### `.github/workflows/python-app.yml`
- Triggers: push / pull_request to `main`.
- Declares least-privilege `permissions: contents: read` ✅.
- Uses `actions/setup-python@v5`, Python 3.11, pip cache ✅.
- Installs the lean `requirements-dev.txt` (fast, reliable) and runs the flake8
  syntax gate + full pytest ✅.
- **Remaining recommendation:** pin first-party actions (`actions/checkout`,
  `actions/setup-python`) to a full commit SHA for supply-chain hardening.

### `.github/workflows/deno.yml` — REMOVED
- Deleted in the 2026-06 upgrade. There was no Deno source in the repository, so
  `deno lint` / `deno test` ran against nothing. See `docs/DECISIONS.md`.

## General hardening checklist (for new/changed workflows)

- [ ] Add an explicit least-privilege `permissions:` block to every workflow.
- [ ] Avoid `pull_request_target` unless absolutely required; if used, never
      check out and run untrusted PR code with secrets in scope.
- [ ] Treat PR titles, branch names, issue/PR bodies, and commit messages as
      **untrusted input** — never interpolate them into `run:` shell steps.
      Pass them via `env:` and quote, or use actions that handle them safely.
- [ ] Pin third-party actions to a full commit SHA, not a moving tag.
- [ ] Never upload broad artifacts (`path: .`); upload only specific outputs.
- [ ] Scope secrets to the jobs that need them.

## Supply chain

- `.github/dependabot.yml` configures weekly updates for pip (root, backend,
  doto), npm (frontend, mineral_deal_room) and github-actions, with security
  updates grouped separately from routine version bumps.
- A `CODEOWNERS` file is recommended so workflow/dependency changes require
  review (see `docs/ROADMAP.md`).
- SBOM generation (e.g. `cyclonedx`/`syft`) is optional and deferred; practical
  to add later per-ecosystem if needed.
