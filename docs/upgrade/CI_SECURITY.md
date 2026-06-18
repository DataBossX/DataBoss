# CI / GitHub Actions Security Notes

## Current workflows

### `.github/workflows/python-app.yml`
- Triggers: push / pull_request to `main`.
- Already declares least-privilege `permissions: contents: read` ✅.
- Runs flake8 syntax gate + pytest.
- **Recommendations:**
  - Pin third-party actions by commit SHA where practical. `actions/checkout`,
    `actions/setup-python` are first-party; pinning to SHA is still best practice
    for supply-chain hardening.
  - `actions/setup-python@v3` is older — bump to `@v5`.
  - Consider caching pip and installing `requirements.txt` reliably (the heavy
    OCR deps may need system libs; keep the unit job lean — e.g. install only
    `pytest flake8` plus light deps).

### `.github/workflows/deno.yml`
- Triggers: push / pull_request to `main`.
- **There is no Deno source in this repository.** `deno lint` / `deno test`
  operate on nothing meaningful.
- The third-party `denoland/setup-deno` action is already pinned by SHA ✅.
- **Recommendation:** remove this workflow (legacy/no-op) unless Deno code is
  planned. Left in place during this upgrade to avoid changing CI behavior
  without owner sign-off — see `docs/DECISIONS.md`.

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
