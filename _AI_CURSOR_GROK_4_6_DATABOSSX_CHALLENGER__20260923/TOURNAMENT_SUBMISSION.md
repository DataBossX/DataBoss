# DATABOSSX CHALLENGER SUBMISSION — 2026-09-23

AI_NAME: Cursor Grok 4.6 (challenger, not production writer)
MODEL: Cursor Grok 4.6 — jointly trained by SpaceXAI and Cursor
TOOLS ACTUALLY USED:
- local repo read (main @ `582d951`)
- `gh` for open/draft PRs and issues
- web fetch/search of official provider pages
- file write into this private challenger folder only
DRIVE ACCESS: NO (all eight listed links 403/timeout; no Drive MCP)
WEB RESEARCH: YES
DATE OF RESEARCH: 2026-09-23

ROLE: independent architecture challenger. Production DataBossX files were treated as READ-ONLY. This folder is the only write target.

Legend used below:

- **VERIFIED EXISTING** — present on current `main`
- **BUILT/UNMERGED** — exists in an open/draft PR, not production
- **PROPOSED** — this submission
- **UNKNOWN** — Drive, hardware, or unpublished quota/state

==================================================
1. CURRENT STATE
==================================================

## What DataBossX already does well (VERIFIED EXISTING)

The July 11, 2026 OS blueprint (`docs/DATABOSSX_OS_BLUEPRINT.md`) is the strongest asset in the public repo. It already states the correct operating model:

- local-first modular monolith
- source > model
- field-level provenance
- exact rational interest math
- one orchestrator / one writer
- deterministic work never routes to an LLM
- model agreement is not evidence
- no Redis/Celery/Kafka/vector DB until measured need

Working code on `main` that should be reused, not rebuilt:

| Asset | What it already does | Deficiency |
| --- | --- | --- |
| `grocery_report_pipeline.py` | Deterministic A–I inventory → classify → extract → reconcile → validate → report. LLM is opt-in (`--use-llm`). Synthetic tests exist. | Single file. Regex extract is weak on scans. Real corpus never ran in cloud. |
| `horizon/` | Exact fraction math, OGL↔runsheet chaining, workbook versioning, controlled loop, human release gate. Broad pytest coverage. | Can move duplicates to `trash` (blueprint forbids original moves). Repair path has known Issue #94 defects on main. |
| `src/databossx/` | SQLite WAL, content-addressed vault, local intake, SHA-256 inventory, template registration, seed tasks, `/healthz` API. Tests in `tests/test_databossx_foundation.py`. | Kernel only. No claims graph, no real workers, no router, no governor on main. |
| `doto_image_commander/` | County pull queue, page images, audit log, spend table, Streamlit UI. | Hard-wired to OpenAI `gpt-4o`, whole-page vision, stale May-2025 cost formula, 5 pages/call, giant prompt every time. |
| `horizon/controlled_loop.py` | Manifest-bound QA, one-defect repairs, hash-bound human release. | Not the title authority. Must stay a workbook tool. |
| `automation/roger_mills_title_report_builder.py` | Deterministic workbook “tournament” to pick a base report. | Project-specific. Not a model tournament. |

## What exists only off-main (BUILT/UNMERGED — do not treat as production)

| PR | What it claims | Status 2026-09-23 |
| --- | --- | --- |
| **#107** routed engine | Batch leases, recipe cache, field candidate compare (majority ≠ evidence), policy-first router, sealed receipts | OPEN — closest match to this mission |
| **#114** trusted kernel + Drive sync | Issue #94 fail-closed fixes, claims/evidence tables, read-only Drive connector, CLI, policy engine | OPEN, updated today |
| **#99** title verifier | Legal-desc / date / interest / chain validators | DRAFT |
| **#100** Control Tower | Heavy ceremony: 26 invariants, sha256 sidecars of sidecars, Gate 0 packets | DRAFT — high process, low product leverage |
| #54 Landman Helper | PARKED as duplicate | CLOSED |
| #68 issue | “Continuous Improvement Governor” | OPEN issue, not implemented on main |
| #2 / #72 / #93 | Leaked keys + publication hold | Still OPEN |

`main` last updated **2026-07-18**. September Drive docs (router/governor, Landman Helper, skill register, dispatch outbox) are **UNKNOWN**.

## Duplicated, underused, or inefficient

1. **Writer explosion.** 100+ PRs. Many PARKED/QUARANTINED as duplicates (Landman, Control Tower, Land Intelligence, Title Intelligence, watchers). The tournament is violating ONE MUTABLE TARGET = ONE WRITER.
2. **Two `002_*.sql` migrations** (#107 engine tables vs #114 kernel tables). They will collide. This is the current merge bomb.
3. **Hardcoded quality scores in PR #107** (`local.ocr.v1` quality 0.72, `remote.extract.llm.v1` 0.80). Those numbers are invented. They must start as UNKNOWN until a Ryan-task benchmark writes them.
4. **DOTO whole-document premium vision** is the live spend leak if still used. One high-detail `gpt-4o` call for up to 5 pages, full extraction prompt every time, no field packets, no local OCR first.
5. **`backend/server.py` mock OCR** still fabricates legal-looking text with confidence 0.95. Blueprint already said retire it. Still on main.
6. **Control Tower receipt theater** (PR #100) multiplies JSON/sha256 artifacts without extracting a single title field.
7. **No model registry, no governor, no Ollama/LM Studio/llama.cpp adapter on main.** Those are PROPOSED or Drive-UNKNOWN, not built.
8. **Website “Agent Tournament”** is marketing, not an engine.
9. **Hardware UNKNOWN.** Any claim that a specific local model “fits Ryan’s PC” is false until a hardware receipt exists.
10. **Security still P0.** `backend/.env` history + Issue #2 Zhipu key. Local-first is theater if keys live in git.

==================================================
2. THE 10 BIGGEST ARCHITECTURE IMPROVEMENTS
==================================================

Only items that raise capability, cut spend, or both. PROPOSED unless noted.

1. **Field-packet extraction, not document-packet LLMs.** Split every instrument into typed fields with source hash + page + bbox/offsets. Escalate only `UNKNOWN` / `CONFLICT` / `UNSUPPORTED` fields. This is the spend killer. Capability gain: auditability. Cost gain: 70–95% fewer premium tokens on typical abstracts (estimate; measure on a 20-doc gold set).

2. **Land the already-written disagreement engine, do not rewrite it.** Cherry-pick PR #107 `candidates.py` + `cache.py` + `receipts.py` + `routing.py` onto one writer branch. Majority vote remains non-evidence. Distinct sourced values stay `CONFLICT`.

3. **Replace invented route scores with a live evaluation table.** Model registry rows start `status=CHALLENGER`, `quality=UNKNOWN`. Promotion requires task-specific gold scores. A new model enters by ID + adapter + eval, not by rewriting DataBossX.

4. **Deterministic OCR first; vision second; LLM third.** Tesseract / PaddleOCR / PDF text layer on CPU. Local VL only on low-confidence pages. Remote vision only on remaining pages. DOTO currently inverts this.

5. **Prompt packets: GLOBAL / PROJECT / TASK / SOURCE / SCHEMA.** Ryan’s rules stay. They are stored once, hashed, and cache-addressed. Do not resend the master prompt with every page.

6. **Owner-supplied allowance governor — no guessed quotas.** Modes: `LOCAL_ONLY`, `FREE_ONLY`, `ECONOMY`, `BALANCED`, `QUALITY_FIRST`. Hard-code nothing about ChatGPT/Claude/Gemini/Cursor message caps. Those are UNKNOWN/VARIABLE. The owner types remaining allowance; the governor only consumes what it is told.

7. **One merge train.** Freeze overlapping production mutation. Resolve #107 vs #114 `002_*.sql` before any new kernel is written. Issue #56 already asked for this. It was not done.

8. **Kill mock OCR and stale gpt-4o pricing on any path that can touch client bytes.** Fail closed if the worker is `demo_ocr`. Refresh cost tables from a versioned price file, not comments from May 2025.

9. **Phone = read-only status over a private tunnel.** Loopback API + Tailscale/WireGuard (or equivalent). Show queue, models, disagreements, budget, failures, approvals. Do not expose Ollama/LM Studio to the public internet. Landman Helper direction is UNKNOWN from Drive; parked PR #54 must not be revived as a second control plane.

10. **Ryan-task benchmark harness before any more model shopping.** 15–30 examiner-reviewed fields from a real (private) abstract beat every public leaderboard. Winners are per task. No universal ranking.

==================================================
3. BEST LOCAL-MODEL STRATEGY
==================================================

Move local first by task class, not by “run the biggest GGUF.”

**Ryan hardware = UNKNOWN. Treat the table as a candidate ladder, not a purchase list.**

### Move local FIRST (high volume, structured, privacy-sensitive)

| Task class | Why local-first | Candidate stack (unverified on Ryan’s box) |
| --- | --- | --- |
| Inventory, hash, dups | Already local and correct | Keep `src/databossx` + grocery B |
| Classification of known instrument types | Keyword/rules already work | Keep grocery D; small local text model only on leftovers |
| Party / date / instrument-number / STR | Regex + gazetteer + title_verifier | PR #99 validators + grocery E |
| Interest math / chain / conservation | Exact fractions. LLM will fail. | `horizon/interest.py`, `horizon/chaining.py`, PR #114 `titlemath.py` |
| Spreadsheet QA / OOXML integrity | Deterministic | `horizon/workbook_qa.py`, controlled loop |
| Duplicate / contamination | Hash + normalized legal + party keys | Existing inventory + FTS5 later |
| PDF text-layer extraction | Free, exact | pdfplumber / PyMuPDF |
| Scan OCR (typed county pages) | Volume + privacy | Tesseract or PaddleOCR-VL-1.5 (~3 GB class; hardware UNKNOWN) |
| Page-image field read | High volume | Qwen3-VL 4B/8B via Ollama/llama.cpp **if** VRAM/RAM receipt allows |

### Keep cheap-remote SECOND

- Gemini 2.5 Flash / 3.8 Flash **paid** (free tier trains on prompts — usually forbidden for client abstracts)
- DeepSeek Flash off-peak (vision on Flash; Pro has no vision)
- Qwen3.8 Flash / Qwen VL APIs
- Mistral OCR 4.1 only as a specialist page worker, not a reasoning model

### Keep premium LAST

- Claude Sonnet 5 / Opus 5, GPT-5.6 Terra/Sol, Grok 4.6, Gemini 2.5 Pro
- Only for unresolved field packets + minimum source crop
- Never for title math, hashing, workbook compare, or whole abstracts

### Do not local-first yet

- Novel legal-theory / curative strategy (human landman + optional premium)
- Web research of current case law / BLM (remote, cited)
- Unreadable manuscript / faint scan after local OCR+VL fail

==================================================
4. MODEL / TASK ROUTING MATRIX
==================================================

**No universal ranking.** Hardware unverified. Prices are official 2026-09-23 reads unless marked. Subscription message caps: UNKNOWN/VARIABLE.

Price unit: USD / 1M tokens unless noted. Peak DeepSeek = 2× off-peak.

| TASK | BEST LOCAL CANDIDATE | BEST LOW-RESOURCE LOCAL | BEST FREE/LOW-COST REMOTE | BEST VALUE PAID | PREMIUM ESCALATION | ESCALATION TRIGGER |
| --- | --- | --- | --- | --- | --- | --- |
| Inventory / hash / dups | Existing Python SHA-256 | same | n/a | n/a | n/a | never |
| Instrument classification | grocery keyword rules | Qwen3 4B/8B if leftover | Gemini 2.5 Flash **paid** | Qwen3.8 Flash $0.15/$0.47 | Sonnet 5 | rules + small model disagree AND both cite different types |
| OCR typed scans | PaddleOCR-VL-1.5 or Tesseract | Tesseract CPU | Gemini Flash **paid** page image | Mistral OCR 4.1 **$4 / 1000 pages** | GPT-5.6 Terra / Qwen VL Max | local OCR confidence low OR legal-desc charset garbage |
| OCR faint/hand/stamps | Qwen3-VL 8B/32B if VRAM allows | Qwen3-VL 4B | DeepSeek Flash (vision) off-peak $0.15/$0.60 | Qwen VL paid | GPT-5.6 Sol or Claude Sonnet 5 | two local/cheap vision reads disagree on a material token |
| Party / name extract | regex + gazetteer | small local instruct | DeepSeek Flash | Qwen3.8 Flash or Gemini 2.5 Flash $0.30/$2.50 | Sonnet 5 | normalization collision or suffix/estate language |
| Date extract | regex + chronology checks (#99) | same | DeepSeek Flash | Gemini 2.5 Flash | Sonnet 5 | execution vs recording vs effective conflict |
| Legal description / STR | regex + #99 verifier | Qwen3-VL on the caption crop only | DeepSeek Flash | Qwen VL / Gemini 2.5 Flash | Claude Sonnet 5 or Grok 4.6 | quarter-call mismatch or dual tracts |
| Spreadsheet populate | grocery + Horizon writers | n/a | n/a | cheap model only for header mapping | premium never writes cells | human approval of range + hash |
| Spreadsheet QA | Horizon controlled loop | n/a | n/a | n/a | n/a | never — deterministic |
| Duplicate / contamination | hash + normalized keys | small embed later **only if FTS5 loses** | n/a | n/a | n/a | only after lexical miss is measured |
| Source reconcile | Horizon chaining | n/a | cheap model to propose link, never to close it | DeepSeek Pro off-peak $0.66/$1.98 | Opus 5 / GPT-5.6 Sol | two sourced chains remain after math |
| Coding / debug DataBossX | local GPT-OSS 20B / Qwen3-Coder **if** RAM allows | Qwen3 8B/14B | Grok 4.3 $1.25/$2.50 or Gemini 3.8 Flash $0.75/$3.75 intro | Cursor Grok 4.6 (this lane) | GPT-5.6 Sol / Claude Opus 5 / Grok 4.6 | failing test after two cheap attempts |
| Agent planning | deterministic task graph | small local planner | Gemini 3.8 Flash paid | Sonnet 5 $2/$10 | Opus 5 / GPT-6 Astra $10/$50 | cycle detected or policy conflict |
| Long-context abstract read | **do not**. Page + field packets | n/a | Gemini long context **paid** on TOC/index only | Gemini 2.5 Pro $1.25/$10 ≤200k | GPT-5.6 Terra 1.05M ctx | index pass cannot locate the page |
| Research (public) | local search of vault + FTS5 | n/a | Gemini free **only for non-client public queries** | Gemini grounding after free 5k/mo | premium + citations | local vault miss |
| Adversarial review | second cheap model + deterministic checks | small local critic | DeepSeek Flash independent pass | Sonnet 5 | Opus 5 / GPT-6 Astra | material legal effect still disputed |
| Title math | Horizon fractions | n/a | n/a | n/a | n/a | **forbidden** |

### Official remote price anchors (2026-09-23)

| Provider | Model | Official in/out | Notes |
| --- | --- | --- | --- |
| OpenAI | `gpt-6-luna` | $0.10 / $0.50 | cheap OpenAI workhorse |
| OpenAI | `gpt-6-sol` | $2 / $10 | mid |
| OpenAI | `gpt-6-astra` | $10 / $50 | premium escalation |
| OpenAI | `gpt-5.6-luna` | $0.20 / $1.20 | still listed |
| OpenAI | `gpt-5.6-terra` | $2 / $12 | from models/changelog family; confirm at call time |
| OpenAI | `gpt-5.6-sol` | $4 / $20 | promo at least through 2026-11-21 |
| Anthropic | Claude Haiku 4.5 | $1 / $5 | cheap Claude |
| Anthropic | Claude Sonnet 5 | $2 / $10 | intro became standard |
| Anthropic | Claude Opus 5 | $5 / $25 | 1M ctx, thinking on |
| Anthropic | Claude Fable 5.1 | $10 / $50 | last-resort premium |
| Google | Gemini 2.5 Flash | $0.30 / $2.50 | official Cloud/AI price card |
| Google | Gemini 2.5 Pro | $1.25 / $10 (≤200k) | $2.50 / $15 (>200k) |
| Google | Gemini 3.8 Flash | $0.75 / $3.75 intro through 2026-12-31 | free tier exists; **trains on data** |
| xAI | `grok-4.3` | $1.25 / $2.50 | 1M ctx |
| xAI | `grok-4.6` | $2 / $6 (<200k) | 500k ctx; $4 / $12 ≥200k |
| DeepSeek | `deepseek-flash` (V4.1-Flash) | $0.15 / $0.60 off-peak | vision yes; cache hit $0.003 |
| DeepSeek | `deepseek-v4-pro` | $0.66 / $1.98 off-peak | **no vision** |
| Alibaba | `qwen3.8-flash` | $0.15 / $0.47 intl | |
| Alibaba | `qwen3.8-max` | $2 / $6 intl | 1M free trial tokens 90 days |
| Mistral | Large 3 | ~$0.50 / $1.50 | open-weight also |
| Mistral | OCR 4.1 | **$4 / 1000 pages** | specialist |
| Mistral-hosted | GLM 5.2 | $1.40 / $4.40 | |

Gemini **free** tier: tokens listed free of charge, but “Used to improve our products = Yes.” Exact RPD/RPM: **UNKNOWN / VARIABLE**. Do not put client abstracts on it.

ChatGPT Plus/Pro, Claude Pro/Max, Google AI Pro/Ultra, Cursor Pro/Pro+/Ultra: dollar prices public; **message quotas UNKNOWN / VARIABLE** (providers say no fixed message count).

==================================================
5. TOURNAMENT DESIGN
==================================================

Do not run 12 models on a whole deed.

## Workers per document

```
SOURCE PAGE
  → T0 deterministic OCR / PDF text          (1 worker, required)
  → T0 regex/gazetteer extract               (1 worker, required)
  → T1 small local VL or text, page-crop     (0–1 worker; skip if T0 complete + high OCR conf)
  → T3 cheap remote, page-crop, policy OK    (0–1 worker; only if T0/T1 incomplete)
Independent answers land as Claim candidates.
T0 validators (dates, STR, fractions, book/page) run on every candidate.
Agreement engine is deterministic.
Referee (T4/T5) sees ONLY disputed fields + cropped evidence.
```

Default cheap/local worker count: **2 extractors + 1 deterministic validator**.
Third extractor only if the first two disagree on a material field.
Referee: **1**, never a committee.

## Judge / referee

The judge is **not** a model.

1. Schema-valid JSON or reject.
2. Every field must carry `source_sha256`, page, and span/bbox. Else `UNSUPPORTED`.
3. Identical normalized value + same source span → merge (not “vote”).
4. Different values, both sourced → `CONFLICT` (keep both).
5. One sourced, one unsourced → keep sourced; discard unsourced.
6. Title math / chain / workbook compare never accept an LLM value.
7. Human examiner resolves material `CONFLICT`. Models may annotate, not close.

## Exact escalation triggers

Escalate a **field packet** (not the document) when ANY of:

- `CONFLICT` on a material field (party, legal, date, instrument no., interest, recording ref)
- All extractors returned `UNKNOWN` on a material field and OCR conf < owner threshold (default 0.80, tunable)
- Validator fail (date order, impossible STR, non-exact interest string)
- Cross-document contamination suspected (same text hash on two instrument numbers)
- Owner tagged the project `QUALITY_FIRST` AND the field is on the material list

Do **not** escalate when:

- 2+ sourced extractors agree and validators pass
- Field is non-material (stamp noise, clerk scribble) unless owner list says so
- Allowance mode is `LOCAL_ONLY` or remaining premium allowance is 0 → queue for human instead of failing the run

## Receipt

Every tournament run writes a sealed receipt (PR #107 already has this pattern):

`run_id, page_hash, fields_total, fields_agreed, fields_conflict, fields_unknown, workers, tokens, cost, escalations, receipt_sha256`

==================================================
6. COST-SAVING DESIGN
==================================================

Ryan can drop subscription tiers **if and only if** DataBossX stops using those subscriptions as the production OCR/extract engine.

### What to stop doing

- Whole-abstract paste into ChatGPT / Claude / Gemini / Cursor
- DOTO `gpt-4o` high-detail 5-page dumps
- Resending the master rulebook on every call
- Using free Gemini/ChatGPT for client documents (training / retention risk)
- Paying Ultra/Max so a chatbot can re-read a 200-page abstract

### What to keep (recommendation only — Ryan decides)

Keep **one** mid-tier coding/chat subscription for unresolved engineering and hard legal reading (Cursor Pro or Claude Pro or ChatGPT Plus — not all three at Max). Exact current mix: **UNKNOWN**.

Keep **API credits at $0 default**. If an API is later approved, prefer:

1. DeepSeek Flash off-peak + cache
2. Gemini 2.5 Flash **paid** (no-train)
3. Qwen3.8 Flash
4. Mistral OCR 4.1 per page for ugly scans
5. Sonnet 5 / GPT-5.6 Terra / Grok 4.6 only as referee

### How the system stays intelligent after a downgrade

```
T0 tools do 80% of title factory work today if actually run on the Windows corpus.
T1/T2 local models do the next band IF hardware exists.
T3 paid-cheap APIs do ugly pages.
T4/T5 eat only the disagreement tail.
Human examiner remains the release gate.
```

If local hardware cannot run T2, **do not buy a GPU in this tournament.** Run T0 + T3 Flash. That still beats “one Opus on the whole PDF.”

### Governor behavior (PROPOSED)

| Mode | Remote | Premium |
| --- | --- | --- |
| LOCAL_ONLY | blocked | blocked |
| FREE_ONLY | only adapters marked `free` AND `data_used_for_training=false` | blocked |
| ECONOMY | cheap paid, cache-first, batch/off-peak | blocked unless material CONFLICT after 2 cheap workers |
| BALANCED | cheap default | material CONFLICT or validator fail |
| QUALITY_FIRST | cheap still first | escalate sooner on material fields; still never whole-doc |

When owner-entered remaining allowance hits 0: fallback to local + queue `WAITING_HUMAN`. Do not retry premium until the owner adds allowance.

==================================================
7. BENCHMARK DESIGN
==================================================

Winners by **task**. Gold from Ryan’s reviewed work product, not MMLU.

## Corpus (private, never commit)

20–40 pages spanning: typed county image, faint scan, handwritten note, multi-tract legal, spreadsheet fragment, lease + assignment pair, dirty OCR, a known duplicate, a contaminating extra instrument.

Each gold item:

```json
{
  "item_id": "S32-WD-0042-grantor[0]",
  "task": "party_extract",
  "source_sha256": "...",
  "page": 3,
  "bbox": [x0, y0, x1, y1],
  "gold_value": "JANE Q. DOE, a single person",
  "gold_normalized": "DOE, JANE Q",
  "material": true,
  "notes": "examiner accepted 2026-08-.."
}
```

## Per-task metrics

| Metric | Definition |
| --- | --- |
| accuracy | exact-normalized match to gold |
| completeness | non-UNKNOWN / gold-required |
| hallucination rate | value with no supporting span, or span that does not contain the value |
| conflict_purity | % of system CONFULCTs that a human also treated as real |
| latency | p50/p95 wall time |
| resource | CPU/GPU-sec, peak RAM/VRAM if local |
| cost | estimated + actual USD |
| schema_valid | 1/0 |
| provenance_valid | span covers the value |

## Promotion / demotion

- Enter as `CHALLENGER` (shadow: runs, does not route production)
- Promote to `PRODUCTION` for **that task only** after ≥N gold items (start N=30) and hallucination ≤ owner cap (start 0 on material fields)
- Demote on two consecutive evals worse than incumbent, or provider error rate > owner cap
- Deprecation: if a provider slug 404s, mark `RETIRED`, route to fallback list; do not crash the run

## Do not

- Average all tasks into one “best model”
- Promote from a blog benchmark
- Let the incumbent writer score its own model

==================================================
8. TOKEN / CONTEXT OPTIMIZATION
==================================================

Ryan’s detailed prompts are an asset. Split them; do not shrink them into mush.

```
GLOBAL_RULES     hash-addressed, rarely change  (owner laws, no fabrication, one writer)
PROJECT_RULES    jurisdiction, client template, confidentiality, allowed egress
TASK_PACKET      capability, field list, materiality, mode
SOURCE_PACKET    only the page crop / row / OCR span needed
OUTPUT_SCHEMA    versioned JSON schema id
```

Implementation rules:

1. **Cache key** = `recipe_version + sorted(input_hashes) + params` (already in PR #107 `cache.py`).
2. Prompt-cache / prefix-cache on providers that bill hits cheaper (OpenAI cached input, Anthropic cache, DeepSeek cache hit $0.003–$0.022 / 1M, Gemini context cache).
3. **Delta prompts**: “Field GRANTOR on page 3 crop; prior OCR text follows; return schema X.” Never “here is the 12-page bible plus the deed.”
4. **Stable tools as code**, not as prompt: title math, date order, STR parse, book/page, checksums.
5. **Reuse verified claims.** If `DOE, JANE Q` was accepted on instrument 2019-3 page 1, later pages retrieve that claim by hash instead of re-extracting the same caption.
6. **Dedup context:** one OCR text per page hash, shared by all workers.
7. **Small packets:** one field group per call after first disagreement (parties / dates / legal / money).
8. **Structured outputs only.** Prose answers are failed attempts.
9. **No embeddings until FTS5 + structured keys lose a measured retrieval bake-off** (blueprint already said this; keep it).

Expected effect vs current DOTO path: most pages never leave the machine; escalated calls are <2k tokens instead of a 4k-token prompt + 5 high-detail images.

==================================================
9. WHAT THE EXISTING PLAN GETS WRONG
==================================================

Adversarial. Not agreement for its own sake.

1. **The plan is not the bottleneck. Landing is.** The July blueprint already describes the system this tournament is asking for. Writing another bible (including this one) without a merge train is waste. Drive docs from mid-September are UNKNOWN; if they restate the July blueprint, they are duplication.

2. **PR #107’s router is directionally right and empirically dishonest.** Hardcoded `quality=0.72/0.80/0.88` will lock in a fake league table. Ship the machinery with `UNKNOWN` scores or do not ship scores.

3. **PR #100 Control Tower is the wrong center of gravity.** Fail-closed invariants are good. A second OS made of Gate-0 command packets and nested receipts is how DataBossX avoids shipping extraction. Do not merge it as the kernel.

4. **“Local LLM Landman Helper” as a product name is a trap** if it becomes a chat UI that bypasses the task graph. Phone control must be a view of the orchestrator, not a new agent.

5. **Too many tournaments, none field-level.** Workbook base-report tournament, website tournament, Section 32 best-of-best PRs, this multi-AI contest. The missing object is `Conflict` rows on fields, not more narrative winners.

6. **Phase order in the blueprint is slightly wrong for spend.** P4 (routing/workers) is listed after a full trusted kernel. Ryan is burning money **now** in DOTO-style whole-page vision. A thin field-packet + cache + governor can land on the existing grocery/DOTO paths before the full claims graph is perfect.

7. **“Free models” are not free for title work.** Gemini free and many consumer tiers train on content. Policy must treat `data_used_for_training=true` as egress-forbidden for client bytes, even at $0.

8. **Open-weight ≠ runnable.** DeepSeek V4 Pro / Kimi K3 / Llama 4 Scout / Qwen 2.4T-class models are not a laptop strategy. Recommending them as “the local model” without a hardware receipt is how money gets wasted.

9. **Issue #94 and leaked keys are still open.** A model router on a repo that has committed API keys and a mock OCR that invents legal facts is unsafe. Security/correctness on main beats a new league table.

10. **This tournament’s own structure is a risk.** Many independent AIs are one step away from mutating the same files. The instruction “one mutable target = one writer” is correct and is being stressed by the process that wrote it.

==================================================
10. CODEX IMPLEMENTATION DELTA
==================================================

Codex is the assumed single writer. I am not.

Priority: P0 must land before more model work. Acceptance tests are mandatory.

| # | Pri | File / module | Purpose | Acceptance test |
| --- | --- | --- | --- | --- |
| 1 | P0 | Owner ruling + Issue #56 | Freeze other writers. One branch. | Written ruling: only Codex mutates `src/databossx/**`, `migrations/**`, DOTO analyzer |
| 2 | P0 | `migrations/002_engine_and_kernel.sql` | Merge #107 + #114 table intent into **one** 002. Claims, conflicts, cache, route_decisions, usage_ledger, model_registry | Fresh DB applies 001+002; existing foundation tests still pass |
| 3 | P0 | Cherry-pick `src/databossx/candidates.py` from #107 | Field compare: UNSUPPORTED / AGREE / CONFLICT; no auto-winner | Fixture: two sourced different grantors → CONFLICT; one unsourced dropped |
| 4 | P0 | Cherry-pick `cache.py` + `receipts.py` | Recipe cache + sealed receipts | Tamper fails verify; param change misses cache |
| 5 | P0 | `src/databossx/routing.py` | Keep policy filters; **delete invented quality floats** | `local_only` blocks remote; `title_math` never selects an LLM; ranking uses eval table or UNKNOWN |
| 6 | P0 | `backend/server.py` | Fail closed on mock OCR in any non-demo mode | Test: real-upload / default mode raises; no invented parties |
| 7 | P0 | `doto_image_commander/api/openai_client.py` | Stop default whole-doc `gpt-4o`. Adapter interface + cost table file | Test: analyzer without approved remote route does not call OpenAI |
| 8 | P1 | `src/databossx/packets.py` | GLOBAL/PROJECT/TASK/SOURCE/SCHEMA hashes | Same source+schema+task → identical packet hash; changing one rule changes only that hash |
| 9 | P1 | `src/databossx/governor.py` | Modes + owner-supplied allowances + usage ledger | Mode LOCAL_ONLY never emits network; allowance 0 queues WAITING_HUMAN; no default quota constants |
| 10 | P1 | `src/databossx/registry.py` | Model rows: id, provider, modality, license, training_use, status, task_scores | Insert challenger without code change; production route refuses CHALLENGER |
| 11 | P1 | `src/databossx/workers/ocr_local.py` | PDF text → Tesseract → optional local VL | Synthetic scan: text-layer used first; tesseract called only if empty; no network |
| 12 | P1 | `src/databossx/tournament.py` | 2 extract + 1 validate; escalate field packets | 10-field fixture: 9 agree → 0 remote calls; 1 conflict → 1 referee call with crop only |
| 13 | P1 | `horizon/repair.py` + Issue #94 tests from #114 | Do not downgrade `#REF!`; unlabeled dates ≠ recording_date | `tests/test_issue94_integrity.py` green on the writer branch |
| 14 | P2 | `src/databossx/connectors/drive.py` from #114 | Read-only vault sync, dry-run, no share/write | Tests in `tests/test_drive_sync.py`; write denied without hash-bound approval |
| 15 | P2 | `src/databossx/eval/harness.py` | Ryan-task gold runner, shadow mode | Running a new model writes scores; does not change production routes |
| 16 | P2 | `src/databossx/phone_status.py` | Read-only JSON: queue, models, conflicts, budget, failures | Bound 127.0.0.1; no vault bytes in payload |
| 17 | P2 | `doto_image_commander/core/config.py` | Remove hardcoded gpt-4o as the system model | Config loads registry; missing key → local path |
| 18 | P3 | Landman Helper | **Do not start** until #54 disposition + Drive design are read on the Windows box | N/A — read-only recon first |
| 19 | P3 | Control Tower PR #100 | Do not merge as OS. Steal only: stop-flag, lease, sidecar hash | Explicit “not merged” note in ruling |
| 20 | P3 | Embeddings / vector DB | Forbidden until FTS5 bake-off loses | Benchmark receipt required |

==================================================
11. TOP 25 NEXT BEST MOVES
==================================================

Ordered by capability gain, recurring savings, $0, low risk, least duplication.

1. **Appoint one writer (Codex) and freeze the rest.** Highest process leverage. $0. Unblocks everything.
2. **Rotate leaked keys (SECURITY.md + Issue #2).** Capability = not getting the account emptied. $0 besides time.
3. **Fail-close mock OCR on main.** Stops fabricated legal facts. Cherry-pick the #114 guard.
4. **Run grocery + Horizon inventory-only on the real Windows corpus.** Capability jump is evidence, not code. $0.
5. **Turn DOTO off of default whole-page gpt-4o.** Largest recurring AI spend cut if that path is live.
6. **Land one 002 migration merging #107+#114 table needs.** Prevents the next lost week of conflict.
7. **Ship `candidates.py` field CONFLICT logic.** This is the tournament. Already written.
8. **Ship recipe cache + sealed receipts from #107.** Stops re-paying for the same page.
9. **Add `packets.py` so owner rules are not re-sent.** Saves tokens without deleting rules.
10. **Add `governor.py` with owner-typed allowances and five modes.** Enables downgrading subscriptions safely.
11. **Wire Tesseract/pdf text as the first OCR worker.** $0, CPU, known tool.
12. **Port #99 title_verifier checks behind the validator worker.** Dates, STR, fractions. $0.
13. **Close Issue #94 repair defects** from #114 tests. Correctness > models.
14. **Build a 30-field private gold set from one reviewed abstract.** Makes every later model decision cheap.
15. **Eval harness in shadow mode.** New models enter without rewrites.
16. **Price table as data** (`config/model_prices.2026-09-23.json`) refreshed by a fetch script. Kill comment-pricing.
17. **Read-only phone status on loopback + private tunnel.** Do not expose local LLM ports.
18. **Read-only Drive vault sync from #114** after keys are rotated. Do not write Drive.
19. **Measure hardware** (`nvidia-smi` / RAM / OS) into a receipt. Until then, no local-model purchase advice.
20. **If hardware ≥ ~8–12 GB VRAM (UNKNOWN):** trial Qwen3-VL 8B on 20 gold pages. Else skip.
21. **If hardware is CPU-only:** skip T2; use T0 + paid Flash. Do not buy a GPU in this pass.
22. **Enable DeepSeek Flash or Gemini 2.5 Flash paid only after a $0 owner approval and a privacy check.** Recommendation, not a buy.
23. **Mistral OCR 4.1 as optional ugly-page specialist** after local OCR fails — per-page, not per-abstract.
24. **Retire parked duplicate PRs from the mental model** (#54, #100-as-OS, #23, #33, #35). Stop rebasing them.
25. **Only then** consider a Landman Helper UI that **reads** the orchestrator. No new writer.

==================================================
12. SINGLE BEST MOVE
==================================================

**Codex, as the sole writer, should land field-level candidate comparison + recipe cache + sealed receipts (already written in PR #107) on a single 002 migration, then change DOTO/grocery extraction so a page produces field envelopes and only `CONFLICT`/`UNKNOWN` fields may leave the machine.**

That one move:

- uses code that already exists instead of another architecture essay
- cuts the dominant premium token pattern (whole-document vision)
- makes every later local/cheap/premium model a plug-in worker
- gives the phone/governor something real to display (agreed vs disputed vs escalated)
- does not require a GPU purchase, a new subscription, or Drive write access

Do not build a new Control Tower. Do not download a 2T local model. Do not merge overlapping 002 migrations blindly. Do not send another abstract to a Max-tier chat window.

---

## Evidence classification for this submission

| Claim | Class |
| --- | --- |
| Drive bible / router-governor / Landman Helper / outbox contents | UNKNOWN |
| Ryan hardware | UNKNOWN |
| Consumer subscription remaining quotas | UNKNOWN / VARIABLE |
| `main` capabilities listed in §1 | VERIFIED EXISTING |
| PR #107/#114/#99/#100 contents | BUILT/UNMERGED |
| Prices in §4 | VERIFIED RESEARCH 2026-09-23 official pages |
| Field-packet savings 70–95% | PROPOSED estimate — must measure on gold |
| This folder’s recommendations | PROPOSED |
| Implementation of the above | NOT IMPLEMENTED by this challenger |
