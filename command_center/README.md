# DataBossX Land Intelligence — Command Center

A **military-grade Streamlit command center** plus a **CrewAI agent swarm** that
autonomously chains working interests for an oil & gas section (default
`31-12N-24W`, Roger Mills County, Oklahoma) and perfects a cursory title report
through a **self-healing verification loop**.

> **Why the Mathematician is not an LLM.** The Cursor meta-prompt asked for a
> `MathematicianAgent` that checks the working-interest sum against the tract
> acreage. An LLM cannot be trusted to add `1/3 + 5/128` — over a long chain the
> error compounds into a *fabricated* balance, which is worse than no answer. So
> the math here runs on the exact-fraction [`horizon`](../horizon) engine
> (`fractions.Fraction`, never floats). The CrewAI agents **narrate and route**
> the deterministic result; they never compute it.

## Run it

```bash
# from the repository root
py -m pip install -r command_center/requirements.txt
streamlit run command_center/app.py            # the command center UI
```

Windows: double-click **`Run_Command_Center.bat`** in the repo root.

No API key? No problem — it runs in **deterministic mode** and produces the full
report. The LLM swarm is an optional narration layer (see *Optional swarm* below).

### Headless / CLI (no browser)

```bash
python -m command_center --sample                       # synthetic demo corpus
python -m command_center --workbook "31-12N-24W ....xlsx" \
    --template template.xlsx --out REPORT_v001.xlsx --section 31-12N-24W
```

The CLI exits non-zero when any tract needs examiner review — handy for CI gating.

## The self-healing loop

```
INGEST     read the OGL register + runsheet from the workbook          (Ingestion)
AUDIT      chain each tract with exact interest math, 8/8 start         (Title Auditor)
VERIFY     sum each tract's working interest; compare to 8/8 / gross    (Mathematician)
   ├─ ties out ......................................... ✅ balanced
   ├─ interest undetermined → hand delta back to Auditor
   │      Auditor re-reads the runsheet note; if it documents the
   │      interest ("all", "8/8", a fraction) it is adopted as an
   │      ASSUMED value (highlighted yellow) and re-verified ........... 🩹 healed
   └─ over-conveyance / chain break / unresolved gap ................... 🚩 Needs Examiner Review
```

The loop is **bounded and convergent** (default 5 loops): it stops on the first
pass with no undetermined interests, or when no further assumption is supportable.

**No fabrication.** A gap is healed only from what the runsheet actually says. An
over-conveyance (a party conveying more than it holds) is never "balanced" by
inventing a number — it is escalated.

## Files (modular, section-agnostic)

| File | Role |
| --- | --- |
| `engine.py` | The deterministic self-healing loop + telemetry (the brain) |
| `xlsx_writer.py` | Writes the report to Excel; **highlights ASSUMED cells yellow** |
| `agents.py` | The three CrewAI agents (Ingestion, Title Auditor, Mathematician) |
| `tasks.py` | The CrewAI task graph + `run_pipeline()` driver (deterministic-first) |
| `tools.py` | Exact-math tools the swarm calls instead of doing arithmetic |
| `sample_data.py` | Synthetic OGL+runsheet corpus (exercises heal + escalate) |
| `app.py` | The Streamlit command center (dark UI, `#00D8FF`, Orbitron, live console) |
| `__main__.py` | Headless CLI |

Point `--section` / the section box at a different section and the same loop
runs — the engine is not hardcoded to `31-12N-24W`.

## The report

The output workbook uses the canonical Roger Mills column layout and paints:

* **Yellow** — an **ASSUMED** value (a documented assumption; verify before use).
* **Amber** — a row tagged **Needs Examiner Review** (a gap the loop could not heal).

If your branded template carries embedded plats (`xl/media`), pass it as the
template and those images are preserved byte-for-byte — only the data sheet is
rewritten.

## Optional swarm

To add the CrewAI narrative layer, uncomment `crewai` in
`command_center/requirements.txt`, install, and set a model:

```bash
export OPENAI_API_KEY=sk-...        # or LITELLM_MODEL / OLLAMA_BASE_URL for a local model
```

The command center shows live badges for *CrewAI installed* and *LLM key*, and
the swarm's narrative appears beneath the deterministic ledger. Even with the
swarm on, **every number still comes from the exact-fraction engine.**

## Tests

```bash
pytest tests/test_command_center.py -q
```

16 tests cover the healing inference, all three loop branches, exact-math
verification, the yellow-highlight writer, the pipeline driver, and the
no-fabrication guarantee.
