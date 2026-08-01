# MOBILE UX SPEC — DataBossX Command Center

Implementation: `apps/control-center-web/`
Evidence: `evidence/command_center/screenshots/` (7 viewports, `visual_qa_report.json`)

## The five-second test

The most important action must be understandable within five seconds on an
iPhone. Vertical order on the Command screen is therefore fixed:

1. **Hold banner** — sticky, top of viewport, always visible.
2. **Command Core** — spatial telemetry, decorative by contract.
3. **Six questions** — the executive answer, as numbers.
4. **Best Next Move** — one card, with its justification.
5. Everything else, behind progressive disclosure.

Answer first, proof second, technical detail third.

## Navigation

Bottom bar, five destinations: **Command · Projects · Decisions · Jobs · More**.
`More` holds Watchers, Artifacts, Audit, System Health, Policies, and Settings
so the primary bar stays uncrowded. The Decisions badge appears only when
approvals are actually pending.

## The Command Core is never authoritative

The canvas visualization draws projects, writers, watchers, jobs, holds, and
receipts as connected nodes. Every value it draws is **also** rendered as text —
in the legend beneath it and in the cards below. Fallbacks:

| Condition | Behaviour |
| --- | --- |
| `prefers-reduced-motion` | One static frame, no animation loop |
| Manual "Reduce motion" toggle | Same, and it overrides the media query in both directions |
| "Low power" toggle | Canvas hidden, text fallback shown |
| No 2D context available | Same fallback path, automatically |
| No JavaScript | `<noscript>` explains that all state remains readable below |

Verified by the `low-power-no-core` and `reduced-motion` QA cases.

## Voice

- Audio is captured **only while the control is deliberately held**.
- Raw audio is **not retained** after successful transcription.
- The confirmation sheet shows the **transcript** and the **parsed intent** as
  two separate blocks, because the second may be wrong.
- Unresolved fields are shown in a distinct warning block and **disable the
  Confirm button**. Nothing dangerous is inferred.
- Confirming creates a CommandEnvelope. It does **not** execute anything, and
  the sheet says so.
- A text fallback is always available.

## Idempotency in the interface

- A single stable idempotency key per request, reused across retries.
- Buttons disable while a request is in flight.
- The service worker **never** queues a POST for replay — replaying a
  consequential action after reconnect would defeat approval and fencing.

## Accessibility

| Requirement | Implementation |
| --- | --- |
| Touch targets ≥ 44px | `--tap: 44px` on every control; verified per viewport |
| Base font ≥ 16px | 16px root; no control text below 13.5px |
| Visible focus | `:focus-visible` outline, never removed |
| Screen reader | Landmarks, `aria-current`, `aria-labelledby`, `role="alert"` on the hold banner, `aria-live` toast |
| Keyboard | Skip link; push-to-talk responds to Space/Enter; Escape closes the sheet |
| Contrast | Status colours chosen for ≥ 4.5:1 on card backgrounds |
| Motion | `prefers-reduced-motion` plus an explicit toggle |

## Layout rules

- The body **never** scrolls horizontally. Asserted at every viewport;
  `horizontal_overflow_px` must be 0.
- Wide content scrolls inside its own container.
- Fixed docks are opaque where controls sit — a translucent dock lets card text
  bleed through, which reads as broken. Regression-checked via hit-testing and
  `backdrop-filter`.
- The `hidden` attribute always wins (`[hidden] { display: none !important }`),
  because author `display` rules would otherwise beat the UA rule — this caused
  a false "decisions waiting" badge, found by screenshot review and now
  regression-tested.
- 320px: grids collapse to one column.
- Short landscape: the dock returns to normal flow.

## Verified viewports

| Case | Size | Result |
| --- | --- | --- |
| iPhone SE | 375×667 | pass |
| iPhone 13 | 390×844 | pass |
| iPhone Pro Max | 430×932 | pass |
| Narrow | 320×640 | pass |
| Landscape | 844×390 | pass |
| Reduced motion | 390×844 | pass |
| Low power, no Core | 390×844 | pass, fallback engaged |

Per case: 0px horizontal overflow, 6 executive cards, 5 nav buttons, hold banner
pinned at `top: 0` with the FOR REVIEW text, Best Next Move present and titled,
withheld Section 32 move visible as withheld, 0 undersized targets, 0 clipped
cards, 0 wrongly-visible hidden elements.

## Installability

`manifest.webmanifest`: standalone display, `#05070d` theme, SVG plus 180/192/512
PNG icons and a maskable 512. The service worker precaches the shell only —
**control-plane responses are never cached**, because a stale posture that looks
live is worse than no posture. Offline API requests return an explicit `OFFLINE`
error the UI surfaces as an error, not as truth.

## Never done here

Scroll hijacking, text below 16px in body copy, gratuitous particles,
inaccessible neon, animation that hides a hold or a decision, arbitrary shell or
path entry, raw evidence display, or absolute paths in any response.
