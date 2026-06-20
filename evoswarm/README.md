# EvoSwarm

An agent fleet for **DataBoss** — Oklahoma mineral-rights intelligence. It wraps
the existing DataBoss domain (OK County land records, OCR/parse pipeline, the
Target Factory deal room) in a LangGraph-orchestrated swarm with an eval-gated,
human-approved self-improvement loop.

## Quickstart

```bash
git clone <this-repo> && cd evoswarm
./deploy.sh           # local: docker-compose + eval gate
# or
tilt up               # live dev loop (regen specs -> evals -> deploy)
```

Cold-clone friendly: if `langgraph` isn't installed yet, the orchestrator falls
back to a topologically-equivalent sequential runner so tests and the API still
boot.

## Verify

```bash
pip install -e ".[dev]"
python scripts/gen_specs.py    # writes + validates the 12 agent specs
python -m pytest -q            # 6 evals incl. DOI royalty math
uvicorn evoswarm.api:app       # http://localhost:8000/docs
```

## Layout

| Path | What |
|------|------|
| `src/evoswarm/schemas.py` | Pydantic v2 **strict** models — the contract |
| `src/evoswarm/graph.py` | LangGraph orchestrator (+ fallback) |
| `src/evoswarm/oklahoma/` | OK County stub, DOI royalty calc, PostGIS queries |
| `src/evoswarm/evoloop/` | Eval-gated improvement loop (human-PR gated) |
| `specs/*.agent.yaml` | 12 validated agent specs (generated from one manifest) |
| `openapi/evoswarm.openapi.yaml` | OpenAPI exported from the live FastAPI app |
| `helm/evoswarm/` | One chart → API + 12 agent workloads |
| `ARCHITECTURE.md` | Full blueprint, Tree-of-Thought, failure analysis |

## A note on "self-improving"

The EvoLoop does **not** rewrite running production code unsupervised. It scores
candidate prompt/spec diffs against the frozen eval set in `tests/` and, when a
candidate clears the threshold, opens a **pull request for a human to merge**.
See `ARCHITECTURE.md` § Reflection for why that gate exists.
