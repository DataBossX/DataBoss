# Implementation Plan

## Phase 1: Provenance foundation
Build projects, documents, document_files, pages, parties, party_aliases, tracts, extraction_candidates, document_facts, fact_sources, and fact_reviews.

## Phase 2: Instrument normalization
Build instruments, instrument_parties, instrument_tracts, conveyance_legs, reservation_legs, burden_legs, probate_cases, and probate_distributions.

## Phase 3: Deterministic engine
Implement exact Fraction arithmetic, chain ordering, grantor-availability checks, scope intersection, depth and formation filtering, overconveyance detection, gap detection, and balance reconciliation.

## Phase 4: Publication controls
Build calculation_runs, claims, claim_sources, claim_reviews, chain_issues, release_gates, and immutable audit_events.

## Phase 5: Vertical slice
Add CLI commands: project create, ingest, extract, review, normalize, calculate, verify, report.

## Required tests
- exact fraction conservation
- migration apply/rollback
- unsupported claim rejection
- duplicate checksum handling
- party alias resolution
- scope intersection
- chain imbalance
- immutable calculation history
- source-to-output traceability

## Safety
Keep Section 32 HOLD_NO_RELEASE. Do not edit original evidence, merge, deploy, publish, purchase records, or make title conclusions.
