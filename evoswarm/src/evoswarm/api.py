"""FastAPI surface — generates the OpenAPI served at /openapi.json.

`uvicorn evoswarm.api:app` boots the swarm behind a typed HTTP API.
"""

from __future__ import annotations

from fastapi import FastAPI

from evoswarm.graph import build_graph
from evoswarm.oklahoma.royalty import compute_royalty
from evoswarm.schemas import RoyaltyInput, RoyaltyResult, SwarmState, Task

app = FastAPI(title="EvoSwarm", version="10.0.0")
_graph = build_graph()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/tasks", response_model=SwarmState)
def submit_task(task: Task) -> SwarmState:
    return _graph.invoke(SwarmState(task=task))


@app.post("/v1/royalty", response_model=RoyaltyResult)
def royalty(payload: RoyaltyInput) -> RoyaltyResult:
    return compute_royalty(payload)
