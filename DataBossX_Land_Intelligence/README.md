# DataBossX — Land Intelligence

A **local** Streamlit + CrewAI command center that chains mineral/title
ownership for **Section 31‑12N‑24W, Roger Mills County, Oklahoma** (and any
other section you feed it). Upload a runsheet, run the self‑healing title
chain, and export a corrected, formatting‑preserving XLSX.

The core principle: **the LLM may reason, but Python verifies the math.** All
acreage is `Decimal`, every tract total is checked deterministically, and no
tract is ever silently force‑balanced.

---

## Quick start

### Windows

```
run_app.bat
```

It finds Python, creates `.venv`, installs `requirements.txt`, generates the
template if needed, and opens the app at <http://localhost:8501>.

### macOS / Linux

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python make_template.py            # writes data/template/template.xlsx
python make_sample_runsheet.py     # optional: a demo runsheet
streamlit run app.py
```

Then in the browser: upload a runsheet (or use the generated sample), click
**RUN TITLE CHAIN**, watch the live telemetry, and download the corrected
workbook.

---

## What it does

1. **Ingest** a runsheet (`.xlsx`, or `.pdf` if `pdfplumber` is installed) and a
   template `.xlsx`.
2. **Chain** mineral/title ownership tract by tract — deducting interest as it
   is conveyed, carrying OGL numbers down beside leased owners (the *Tract 1*
   pattern), and normalizing assignments to `ASSN`.
3. **Verify** every tract deterministically with `Decimal` (tolerance
   `0.000001`).
4. **Self‑heal**: if a tract does not total to its acreage, the delta and owner
   table go back to the Title‑Auditor agent for a corrected chain — up to **5**
   retries. If it still cannot balance, the best result is exported with an
   explicit **assumption note** and a **yellow review flag** — never a silent
   force‑balance.
5. **Export** into the template, preserving formatting, with the Overview tab
   first and only final owners on the Title Sheet.

---

## Architecture

```
app.py            Streamlit UI (dark / neon, live telemetry, status cards, download)
agents.py         Three CrewAI agents + the LLM factory (OpenAI -> Ollama -> clear failure)
tasks.py          CrewAI Task objects + the self-healing loop orchestration
chaining.py       Deterministic ingestion + title-chaining engine (the workhorse)
verifier.py       Deterministic Decimal verification (the arbiter of the math)
schemas.py        Pydantic contracts (RunsheetInstrument, Conveyance, OwnerInterest,
                  TractChainResult, VerificationResult) — Decimal everywhere
excel_writer.py   Writes results into the template, preserving formatting; yellow
                  only on assumption/review cells
make_template.py       Generates data/template/template.xlsx (Overview / Title Sheet / Register)
make_sample_runsheet.py Generates a realistic demo runsheet
data/input/       Drop runsheets here
data/output/      Corrected report lands here
data/template/    template.xlsx (the write destination)
```

### The three agents

| Agent | Responsibility |
| --- | --- |
| **IngestionAgent** | Extract runsheet rows, notes, legals, OGL references, parties, book/page and tract mapping into JSON. |
| **TitleAuditorAgent** | Chain title by tract, apply ASSN logic, deduct ownership, carry OGL numbers, return **final owners only**. |
| **MathematicianAgent** | Confirm tract totals against the deterministic verifier, surface exact deltas, reject bad chains. |

The deterministic engine always runs; the agents **assist** — they re‑chain a
tract when the deterministic pass can't balance it. This means the app works
end‑to‑end **with or without** an LLM (deterministic‑only mode), and the LLM is
never trusted with the arithmetic.

---

## LLM configuration

Copy `.env.example` to `.env`:

- **`OPENAI_API_KEY`** set → uses OpenAI (`OPENAI_MODEL`, default `gpt-4o-mini`).
- Otherwise, if a local **Ollama** server is reachable at `OLLAMA_BASE_URL`
  (default `http://localhost:11434`) → uses `OLLAMA_MODEL` (default `llama3.1`).
- Neither available → the pipeline runs in **deterministic‑only mode** and says
  so clearly. Building the agents without any model raises a clear error.

API keys are read from the environment and **never** printed, logged, or
written into the output workbook.

---

## The 16 hard title rules — where they live

| # | Rule | Enforced in |
| --- | --- | --- |
| 1 | Template is the write destination | `excel_writer.write_corrected_workbook` |
| 2 | Preserve workbook formatting | `excel_writer._copy_style` / style‑reference row |
| 3 | Overview/map tab stays first | `excel_writer._ensure_sheet_order` |
| 4 | Title Sheet shows only final owners | `chaining.chain_tract` (positive holdings only) |
| 5 | Intermediate owners drop unless retaining | `chaining.chain_tract` |
| 6 | Runsheet notes/legals are controlling | ingestion + `_resolve_tract_acres` |
| 7 | OGL column holds OGL numbers only | `schemas` OGL validators |
| 8 | Never book/page in OGL fields | `schemas.looks_like_book_page` |
| 9 | Assignment conveyance type is `ASSN` | `chaining.to_conveyances` |
| 10 | Carry OGL numbers beside leased owners | `chaining.chain_tract` (`lease_of`) |
| 11 | No owner conveys more than they own | `verifier.find_over_conveyances` + capping |
| 12 | No negative ownership | `verifier.find_negative_holdings` + `schemas` `ge=0` |
| 13 | Each tract totals exactly to acreage | `verifier.verify_tract` (tolerance `0.000001`) |
| 14 | Assumptions only when necessary, noted | `tasks._apply_assumption_balance` |
| 15 | Highlight only assumption/review cells | `excel_writer._write_owner_row` (single yellow fill) |
| 16 | No strange highlights | one `PatternFill`, used only for review cells |

---

## Decimal policy

- Acreage/interest quantized to `0.000001`.
- Negative values rejected at the schema layer.
- Tract totals rejected outside a tolerance of `0.000001`.

---

## Security

- API keys are never printed or logged, and never written to the workbook.
- All inputs and outputs stay on the local filesystem under `data/`.
- No external uploads.

---

## Notes

- PDF ingestion requires `pdfplumber` (in `requirements.txt`); convert to XLSX
  if you'd rather not install it.
- The generated template is a real, styled workbook — replace
  `data/template/template.xlsx` with your own and the writer will target its
  `Overview`, `Title Sheet`, and `Runsheet Register` sheets.
