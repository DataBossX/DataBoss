# ADR-0001 — Zero-dependency stack for the Command Center lane

- Status: **Accepted** (reversible)
- Date: 2026-08-01 · Cycle `DBX-CC-10000X-20260801-001`

## Context

The directive prefers a TypeScript/React/Vite PWA and a Python API. Both require
package installation. Measured in this environment:

```
pip install pytest   -> ERROR: No matching distribution found (no PyPI route)
npm view react       -> npm error 403 forbidden by security policy
```

Neither registry is reachable. A stack that cannot be installed cannot be
compiled, linted, tested, or screenshotted here — and the directive forbids
claiming tests passed when they did not run.

## Decision

Build the entire Command Center slice on the Python standard library and
dependency-free browser code.

- Control kernel, API, runner, Drive bridge, watchers: Python stdlib + `sqlite3`.
- PWA: hand-written HTML, CSS, and ES2020 with no build step.
- Tests: `unittest`.
- Visual QA: headless Chromium driven over CDP through a stdlib WebSocket
  client (`scripts/cdp_client.py`), since Playwright cannot be installed.
- PNG icons: generated with `zlib` + `struct`, since Pillow cannot be installed.

## Consequences

**Positive**

- Everything actually runs here: 154 tests execute, 7 viewports screenshot.
- No supply-chain surface, no lockfile drift, no transitive CVEs.
- The strict CSP (`script-src 'self'`, no `unsafe-inline`) is achievable because
  there is no bundler injecting inline code.
- Runs air-gapped, which suits a private control plane on a local runner.

**Negative**

- No React ecosystem; UI state is managed by hand. Acceptable at this screen
  count, and it would not survive much growth.
- No `pytest` fixtures/plugins.
- Hand-rolled CDP client covers only the subset of RFC 6455 that CDP needs.

## Migration seam

Nothing in `services/control_api/command_center/` imports browser code, and the
PWA speaks only JSON over the documented HTTP routes. Replacing the client with
React/Vite is a client-side change; replacing `http.server` with FastAPI is a
transport change. Neither touches the kernel's invariants.

## Reversal condition

When a networked runner is available, re-run this decision. The PWA is the
first candidate to migrate; the kernel has no reason to change.
