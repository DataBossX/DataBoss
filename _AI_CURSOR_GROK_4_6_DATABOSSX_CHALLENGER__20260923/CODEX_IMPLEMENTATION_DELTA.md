# Codex implementation delta — sole writer

Challenger: Cursor Grok 4.6 — 2026-09-23
Authority: PROPOSED only. This file is not a merge.

Single best move: land PR #107 field-compare + cache + receipts on one 002 migration, then stop whole-document LLM extraction.

## Do not

- Merge PR #100 as the OS
- Open a second `002_*.sql`
- Invent quality scores
- Hard-code ChatGPT/Claude/Gemini/Cursor quotas
- Expose Ollama/LM Studio publicly
- Buy APIs, GPUs, or subscriptions
- Write to Ryan’s Drive control files
- Mutate client evidence

## P0 tickets

### T-P0-1 Freeze writers
- File: owner ruling (Drive, not this repo)
- Test: written “Codex-only” target list

### T-P0-2 One migration
- File: `migrations/002_engine_and_kernel.sql`
- Purpose: union of #107 engine tables + #114 claims/evidence/connectors
- Test: `001` + `002` apply on empty DB; `tests/test_databossx_foundation.py` pass

### T-P0-3 Field compare
- File: `src/databossx/candidates.py` (cherry-pick #107)
- Test: sourced disagreement → CONFLICT; unsourced dropped; no auto-winner

### T-P0-4 Cache + receipts
- Files: `src/databossx/cache.py`, `src/databossx/receipts.py`
- Test: hit on identical recipe; miss on param change; tamper fails

### T-P0-5 Honest router
- File: `src/databossx/routing.py`
- Change: keep policy filters; remove hardcoded 0.72/0.80/0.88
- Test: local_only blocks remote; title_math never LLM

### T-P0-6 Kill mock OCR
- File: `backend/server.py`
- Test: default/real-upload refuses `demo_ocr` and emits no party names

### T-P0-7 DOTO stop-default-gpt-4o
- Files: `doto_image_commander/api/openai_client.py`, `doto_image_commander/core/config.py`
- Test: no OpenAI call without an approved remote route + owner mode ≠ LOCAL_ONLY

## P1 tickets

### T-P1-1 Prompt packets
- File: `src/databossx/packets.py`
- GLOBAL / PROJECT / TASK / SOURCE / SCHEMA
- Test: stable hashes; one-rule edit changes one hash

### T-P1-2 Governor
- File: `src/databossx/governor.py`
- Modes: LOCAL_ONLY, FREE_ONLY, ECONOMY, BALANCED, QUALITY_FIRST
- Allowances: owner-supplied only
- Test: allowance 0 → WAITING_HUMAN, not retry storm

### T-P1-3 Registry
- File: `src/databossx/registry.py`
- Test: CHALLENGER cannot be selected for production

### T-P1-4 Local OCR worker
- File: `src/databossx/workers/ocr_local.py`
- Test: text-layer first; Tesseract only if empty; no network

### T-P1-5 Tournament
- File: `src/databossx/tournament.py`
- Test: 9/10 agree → 0 remote; 1 conflict → 1 cropped referee packet

### T-P1-6 Issue #94
- Files: `horizon/repair.py` + `tests/test_issue94_integrity.py` from #114
- Test: that suite green

## P2 tickets

- Drive read-only sync from #114
- Eval harness / shadow challenger
- Loopback phone status JSON
- Versioned price file (no comment prices)

## Done when

A synthetic 10-field document run on the writer branch produces a sealed receipt with `fields_agreed`, `fields_conflict`, `escalations`, and **zero** remote calls on the agreed set.
