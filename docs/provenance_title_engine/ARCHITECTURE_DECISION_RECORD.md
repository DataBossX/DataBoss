# DataBossX Provenance-First Title Engine

Status: Proposed

## Decision
Build a deterministic, provenance-first title engine as a separate bounded system from the multi-agent control plane.

## Non-negotiable rules
- No publishable title conclusion without source evidence, immutable calculation-run history, and review status.
- Exact rational arithmetic only for title fractions.
- LLMs may classify and extract candidate facts; they may not calculate ownership, WI, NRI, ORRI, or HBP.
- OCR, candidate extraction, reviewed fact, instrument effect, deterministic calculation, and published claim remain separate layers.
- Prior calculations and facts are immutable; corrections create superseding records.
- Duhig, after-acquired title, overconveyance, reservation conflict, and probate issues are flagged for review rather than silently adjudicated.

## Initial vertical slice
Use synthetic and controlled Beckham County fixtures covering patent, deeds, mineral reservation, probate, lease, assignment, release, depth limitation, and one unresolved gap.

## Out of scope
- Processing all 4,893 Section 32 images
- Client report release
- Automatic legal interpretation
- PR merge or production deployment
