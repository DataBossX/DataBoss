# DataBoss — Autonomous Landman Intelligence Blueprint (2026)

**Status:** Working blueprint, grounded in the actual repository.
**Last updated:** 2026-06-22.
**Scope:** A buildable, honest plan to turn DataBoss from a demo into a real,
self-improving system for landman / mineral-rights work (chain of title, lease
and deed extraction, county-records automation), and a roadmap for the broader
"ecosystem" ambition — without the hand-waving.

---

## 0. Why this rewrite exists (read this first)

The previous blueprint read well but was not safe to build from. The specific
problems, and what this document does instead:

| Previous blueprint claim | Reality | This document |
|---|---|---|
| "Claude 4.5 Sonnet (Claude Code)", "GPT-5 Codex", "Gemini 2.5 Pro" are the best 2026 models | Those IDs are wrong or outdated. As of mid-2026 the frontier Anthropic model is **Claude Opus 4.8** (`claude-opus-4-8`). | Uses real, current model IDs and real per-token prices (§2). |
| "Boba by stealth … ahead of Claude Opus 4.6", "Qwen3.7 Max", "GLM-5.2" with "arena scores" | No verifiable evidence these exist. They look like hallucinations dressed up with a fake ranking. | Drops all unverifiable models. Recommends only models we can name, price, and call. |
| Citation `【479210004233043†L166-L164】` | A fabricated citation artifact. | No fake citations. Claims are either checkable or marked as assumptions. |
| "Extend AI achieves 95%+ accuracy", "OCR cuts errors by 80%" | Vendor-marketing numbers with no audit. Treating them as fact is how you mis-scope a project. | Treats vendor accuracy as **unverified until benchmarked on your own documents** (§4). |
| Nine frameworks, "weekly tournaments", "self-evolving empire" | Architecture-astronaut scope. None of it touches the real repo, which has mock OCR and a stub parser. | Starts from what the repo actually is, fixes it, then layers ambition in phases (§7). |

The guiding principle: **a smaller system that actually extracts a deed
correctly beats a ten-agent "empire" that processes mock text.**

---

## 1. What DataBoss actually is today

A landman / mineral-rights document pipeline. Current real components:

- **`backend/server.py`** — FastAPI app. Uploads documents, runs **mock OCR**
  (returns canned text), then calls LLMs. Model IDs are stale
  (`gpt-4`, `claude-3-sonnet-20240229`, `gemini-pro`). SQLite via `aiosqlite`.
- **`automation/`** — `playwright_bot.py` (Weld County, CO recorder scraping),
  `parsing.py` (a regex stub standing in for LLM extraction), `status_logic.py`,
  `writer.py`.
- **`mineral_deal_room/`** — a Vite/React "Target Factory" front end.
- **`doto_image_commander/`** — Oklahoma county land-records automation app.
- **`config/settings.toml`** — Weld County Sec 1 T7N R63W run config; references
  `anthropic:claude-3-5-sonnet` and `openai:gpt-4o`.
- **`prompts/`** — `extractor_user.md`, `reasoner_user.md`.

### Known defects to fix before adding anything new

1. **OCR is fake.** `process_ocr()` returns a hardcoded string. Nothing is read.
2. **Extraction is a regex stub.** `extractor_llm()` in `parsing.py` never calls an LLM.
3. **Stale model IDs** across `server.py` and `settings.toml`.
4. **Junk files** in `backend/`: `=0.8.0`, `=1.54.0`, `=2.90`, etc. — these are
   the result of `pip install package >=0.8.0` redirecting to a file. Delete them
   and pin real versions in `requirements.txt`.
5. **`README.md` is a one-line placeholder.**
6. **Security:** `CORS allow_origins=["*"]`, no auth, `.env` files committed to git.

These are Phase 0 (§7). Do them first; they are cheap and unblock everything.

---

## 2. Model selection (real, current, priced)

Source of truth for Anthropic models is the `claude-api` skill bundled with this
environment. Prices are USD per 1M tokens (input / output).

| Model | ID | Context | In / Out $/1M | Use for |
|---|---|---|---|---|
| Claude Opus 4.8 | `claude-opus-4-8` | 1M | $5 / $25 | Planning, chain-of-title reasoning, hard extractions, agentic loops. **Default.** |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | 1M | $3 / $15 | High-volume field extraction once prompts are stable. |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 200K | $1 / $5 | Cheap classification (document-type routing), short labels. |
| Claude Fable 5 | `claude-fable-5` | 1M | $10 / $50 | Only the hardest long-horizon work; premium pricing. Opt in deliberately. |

Key API facts (these are where the old code is wrong, and where naive code 400s):

- **Vision + PDF are native.** Claude reads PDFs and images directly via
  `document` / `image` content blocks. For many county scans you may not need a
  separate OCR engine at all — see §4.
- **Thinking is adaptive.** On Opus 4.8 use `thinking={"type": "adaptive"}`. The
  old `budget_tokens` form **returns 400** on 4.7/4.8. `temperature`/`top_p`/`top_k`
  are also rejected on these models.
- **Structured output** via `output_config={"format": {"type": "json_schema", ...}}`
  or `client.messages.parse()` with a Pydantic model — this replaces the brittle
  "return JSON" prompt in `analyze_with_llm()`.
- **Citations** (`citations: {enabled: true}` on a document block) give per-field
  source references — exactly what a chain-of-title audit trail needs. This is a
  first-party capability; you do not need a vendor to "provide citations."
- **Prompt caching** — cache the system prompt + extraction schema + few-shot
  examples; you pay ~0.1× for the cached prefix on every subsequent document.
  For a batch run over a county this is the single biggest cost lever.
- **Batches API** — 50% cheaper, for overnight bulk processing of a county's
  records. Match results by `custom_id`, never by order.

### Model assignment per task

| Task | Model | Why |
|---|---|---|
| Document-type routing (deed/lease/mortgage/release) | `claude-haiku-4-5` | One cheap classification call. |
| Field extraction (grantor, grantee, legal, recording date, book/page) | `claude-sonnet-4-6` with strict JSON schema + citations | Stable, high-volume, needs source refs. |
| Chain-of-title assembly, gap/conflict detection | `claude-opus-4-8`, adaptive thinking | Multi-step reasoning over many linked records. |
| Orchestration / planning | `claude-opus-4-8` | Long-horizon coherence. |

Do **not** spread work across OpenAI + Google + Anthropic "because more is better."
Every extra provider is another SDK, another failure mode, another set of stale
IDs to maintain. Start single-provider (Anthropic) and add others only with a
measured reason (cost, a capability gap, redundancy for a specific step).

---

## 3. Orchestration: pick one, not nine

The old blueprint listed nine frameworks. You do not need a framework zoo. Three
honest options, in order of how much machinery they add:

1. **Plain Anthropic tool-use loop (recommended start).** The `claude-api` SDK has
   a tool runner that drives the agent loop for you. For "classify → extract →
   assemble chain → flag conflicts," a code-orchestrated workflow with a handful
   of typed tools is simpler, cheaper, and easier to debug than any graph DSL.
   You own the loop; the logic lives in readable Python.

2. **Anthropic Managed Agents** when you genuinely need a server-managed, stateful
   agent with a per-session sandbox (e.g. a long-running research agent that reads
   a repo, runs code, and streams progress). This is real and documented; use it
   when the task is open-ended and you want Anthropic to run the loop and host the
   tool sandbox — not as the default for a deterministic extraction pipeline.

3. **A third-party orchestrator (LangGraph, etc.)** only if you hit a concrete need
   the above can't meet (e.g. an existing investment in that ecosystem, complex
   human-in-the-loop branching across many teams). For DataBoss today, this is
   premature.

**Recommendation:** Phases 0–2 use option 1. Revisit option 2 when a landman agent
needs to autonomously work a whole county overnight with checkpoints.

A retrieval/memory layer (the old "LlamaIndex") becomes worth adding when you have
enough processed documents that prior extractions and resolved conflicts should
inform new ones. Until then, your SQLite/Postgres tables *are* the memory. Add a
vector store when you can name the query it answers ("find prior deeds touching
this legal description"), not before.

---

## 4. Document processing — OCR vs. native vision

The most important correction: **before integrating any OCR vendor, test whether
Claude's native PDF/image reading already extracts your fields.** Modern Claude
models read scanned PDFs and images directly. For a large share of typed county
records, the answer is "yes," and you skip an entire vendor dependency.

Decision order:

1. **Native vision first.** Send the page (PDF `document` block or `image` block)
   straight to the model with the extraction schema + `citations`. Benchmark on a
   labeled sample of *your* documents.
2. **Add a dedicated OCR step only for what fails** — heavy handwriting, degraded
   microfiche, dense multi-column tables. Open-source path: Tesseract 5 or
   PaddleOCR, feeding text into the same extraction prompt. Vendor path
   (Extend, Nanonets, Parse AI, AWS Textract, Azure Document Intelligence): treat
   every "95% accuracy" claim as **unverified** until you measure it on your own
   deeds and leases with a real labeled set.
3. **Always keep citations / source offsets.** Chain-of-title work is an audit
   product; every extracted field must point back to where it came from.

**Benchmark before you buy.** Build a labeled set of ~50–100 representative
documents (deeds, leases, mortgages, releases, assignments across your target
counties), define field-level accuracy, and score native-vision vs. each
candidate OCR path on *that*. The procurement decision falls out of the numbers.

---

## 5. Reference: extraction call (replaces the stub in `parsing.py`)

Illustrative — uses current Opus 4.8 surface (adaptive thinking, strict JSON
schema, citations). Tune the schema to your county fields.

```python
import anthropic
from pydantic import BaseModel
from typing import Optional, List

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

class Instrument(BaseModel):
    doc_no: Optional[str]
    instrument_type: Optional[str]      # Deed | Oil & Gas Lease | Mortgage | Release | Assignment
    recording_date: Optional[str]        # ISO 8601
    book: Optional[str]
    page: Optional[str]
    grantor: List[str]
    grantee: List[str]
    legal_description: Optional[str]     # verbatim
    reservations: Optional[str]

def extract_instrument(pdf_bytes: bytes) -> Instrument:
    import base64
    b64 = base64.standard_b64encode(pdf_bytes).decode()
    resp = client.messages.parse(
        model="claude-sonnet-4-6",            # Opus 4.8 for the hard ones
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system="You extract fields from recorded land instruments. "
               "Quote legal descriptions verbatim. If a field is absent, return null.",
        messages=[{
            "role": "user",
            "content": [
                {"type": "document",
                 "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
                 "citations": {"enabled": True}},
                {"type": "text", "text": "Extract the instrument fields."},
            ],
        }],
        output_format=Instrument,
    )
    return resp.parsed_output
```

Notes: `messages.parse()` validates against the schema; the response also carries
`citations` linking fields to page/char ranges for the audit trail. Cache the
system prompt + schema across a batch run. For thousands of records, route the
same call through the **Batches API** at 50% cost.

---

## 6. Security & data governance (non-negotiable, and currently missing)

Land records are public, but the *work product* (client targets, deal analysis,
title opinions) is confidential and sometimes regulated. Current repo posture is
unsafe. Required before any production use:

- **Secrets out of git.** `backend/.env` and `frontend/.env` are committed. Rotate
  any exposed keys, remove from history, load from a secrets manager / env at
  runtime. Keep `.env.example` only.
- **Lock down CORS.** Replace `allow_origins=["*"]` with an explicit allowlist.
- **Authentication + RBAC.** No auth exists. Add OAuth/JWT and role-based access on
  the API before exposing it.
- **Encryption** at rest (DB volume) and in transit (TLS at the proxy).
- **Human-in-the-loop checkpoints** for high-impact output — a chain-of-title
  report should require human review before it leaves the system. Flag gaps and
  conflicting records for a human rather than asserting a clean chain.
- **Audit trail.** Persist citations/source references with every extracted field.
- **Isolation.** Run scrapers and agents with least privilege; respect each county
  site's terms and rate limits (`settings.toml` already has `delay_sec`/`max_concurrent`
  — keep those conservative).

---

## 7. Phased plan (what to actually build, in order)

Each phase is shippable and de-risks the next. Don't skip Phase 0.

**Phase 0 — Make it real and safe (days, not weeks)**
- Delete junk `backend/=*` files; pin real deps in `requirements.txt`.
- Update model IDs everywhere: `claude-opus-4-8` / `claude-sonnet-4-6` /
  `claude-haiku-4-5`; remove `gpt-4`, `claude-3-sonnet-20240229`, `gemini-pro`.
- Remove `.env` from git; rotate keys; fix CORS.
- Write a real `README.md` (what it is, how to run, env vars).

**Phase 1 — Real extraction on one county, one section**
- Replace mock OCR + regex stub with the §5 native-vision extraction call.
- Build the labeled benchmark set (§4) for Weld County Sec 1 T7N R63W.
- Add strict JSON schema + citations; persist source refs in the DB.
- Add `claude-haiku-4-5` document-type routing in front of extraction.

**Phase 2 — Chain of title + review UI**
- Opus 4.8 assembles grantor→grantee chains, detects gaps/conflicts, flags for review.
- Surface results + citations in `mineral_deal_room`; add the HITL approval step.
- Add auth/RBAC.

**Phase 3 — Scale + cost control**
- Batches API for overnight county-wide runs; prompt caching on the shared prefix.
- Expand to more sections/counties; extend `doto_image_commander` (OK) with the
  same extraction core.

**Phase 4 — Autonomy (only after 1–3 are solid)**
- Introduce an orchestrated agent (plain tool-loop, or Managed Agents if the task
  is open-ended) to work a county end to end with checkpoints.
- Add a retrieval/memory layer once prior extractions should inform new ones.
- Continuous evaluation: re-run the labeled benchmark on every prompt/model change
  and gate merges on field-level accuracy. This is the honest version of the old
  "weekly tournaments" — a regression suite, not a vibe.

---

## 8. What "10,000× better" means here

Not ten times the agents. It means:
- **Correct, cited extractions** instead of mock text.
- **Real, current models** instead of fabricated ones.
- **A benchmark you can trust** instead of vendor marketing numbers.
- **A safe, authenticated, auditable system** instead of `CORS:*` and committed secrets.
- **A phased path that ships value early** instead of an empire that never reads a deed.

Build Phase 0 and Phase 1, measure extraction accuracy on real documents, and you
will have leapfrogged the original blueprint — because it would never have read a
single page.
```
