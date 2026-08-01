"""Controlled project memory.

Memory here is typed and sourced. The distinction between *a verified fact*, *an
instruction the operator gave*, and *something a model inferred* is stored
explicitly, because collapsing those three is how a system starts treating its
own guesses as history.

Two hard rules:

* **No private chain-of-thought.** Only concise reasoning summaries, evidence,
  decisions, and receipts are storable. A payload that looks like raw reasoning
  is refused.
* **Nothing is undated.** Every item carries a source and an ``observed_at``, and
  a superseded item is marked, never overwritten.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import MemoryRejected
from .util import Clock, truncate


class MemoryKind(str, Enum):
    VERIFIED_FACT = "VERIFIED_FACT"
    USER_INSTRUCTION = "USER_INSTRUCTION"
    MODEL_INFERENCE = "MODEL_INFERENCE"
    PROPOSED_PLAN = "PROPOSED_PLAN"
    ACCEPTED_DECISION = "ACCEPTED_DECISION"
    SUPERSEDED = "SUPERSEDED"
    REJECTED_CANDIDATE = "REJECTED_CANDIDATE"
    OPEN_QUESTION = "OPEN_QUESTION"


#: Anything that walks like raw reasoning. Summaries are fine; transcripts of
#: deliberation are not stored.
CHAIN_OF_THOUGHT_MARKERS = (
    "<thinking",
    "</thinking",
    "chain of thought",
    "chain-of-thought",
    "let me think step by step",
    "internal monologue",
    "scratchpad:",
)

MAX_STATEMENT_LENGTH = 1000


@dataclass(frozen=True)
class MemoryItem:
    item_id: str
    project_id: str | None
    kind: MemoryKind
    statement: str
    source: str
    observed_at: str
    confidence: float
    superseded_by: str | None = None

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "project_id": self.project_id,
            "kind": self.kind.value,
            "statement": self.statement,
            "source": self.source,
            "observed_at": self.observed_at,
            "confidence": self.confidence,
            "superseded_by": self.superseded_by,
            "is_current": self.superseded_by is None,
        }


class MemoryService:
    def __init__(self, store, clock: Clock | None = None):
        self.store = store
        self.clock = clock or store.clock

    def remember(
        self,
        kind: MemoryKind | str,
        statement: str,
        source: str,
        *,
        project_id: str | None = None,
        confidence: float = 1.0,
        observed_at: str | None = None,
    ) -> MemoryItem:
        kind = MemoryKind(kind)
        if not source:
            raise MemoryRejected(
                "Every memory item needs a source. Unsourced state is not remembered.",
                detail={"kind": kind.value},
            )
        lowered = (statement or "").lower()
        for marker in CHAIN_OF_THOUGHT_MARKERS:
            if marker in lowered:
                raise MemoryRejected(
                    "Refusing to store raw reasoning. Store a concise summary, the evidence, "
                    "the decision, and the receipt instead.",
                    detail={"marker": marker},
                )
        if not statement.strip():
            raise MemoryRejected("Empty memory statement.", detail={"kind": kind.value})

        item = MemoryItem(
            item_id=self.store.new_id("mem"),
            project_id=project_id,
            kind=kind,
            statement=truncate(statement.strip(), MAX_STATEMENT_LENGTH),
            source=source,
            observed_at=observed_at or self.clock.now_iso(),
            confidence=round(float(confidence), 3),
        )
        self.store.execute(
            """
            INSERT INTO cb_memory_items (
                id, project_id, kind, statement, source, observed_at, confidence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.item_id,
                item.project_id,
                item.kind.value,
                item.statement,
                item.source,
                item.observed_at,
                item.confidence,
                self.clock.now_iso(),
            ),
        )
        self.store.audit(
            "memory.recorded",
            "memory_item",
            item.item_id,
            {"kind": item.kind.value, "source": item.source},
            project_id=project_id,
        )
        return item

    def supersede(self, item_id: str, replacement_id: str) -> None:
        """Mark an item superseded. History is appended to, never rewritten."""
        self.store.execute(
            "UPDATE cb_memory_items SET superseded_by = ?, kind = ? WHERE id = ?",
            (replacement_id, MemoryKind.SUPERSEDED.value, item_id),
        )
        self.store.audit(
            "memory.superseded",
            "memory_item",
            item_id,
            {"superseded_by": replacement_id},
        )

    def _rows_to_items(self, rows) -> list[MemoryItem]:
        return [
            MemoryItem(
                item_id=row["id"],
                project_id=row["project_id"],
                kind=MemoryKind(row["kind"]),
                statement=row["statement"],
                source=row["source"],
                observed_at=row["observed_at"],
                confidence=row["confidence"],
                superseded_by=row["superseded_by"],
            )
            for row in rows
        ]

    def current(self, project_id: str | None = None, kind: MemoryKind | None = None) -> list[MemoryItem]:
        query = "SELECT * FROM cb_memory_items WHERE superseded_by IS NULL"
        params: list = []
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if kind:
            query += " AND kind = ?"
            params.append(MemoryKind(kind).value)
        query += " ORDER BY created_at, id"
        return self._rows_to_items(self.store.fetchall(query, tuple(params)))

    def all_items(self, project_id: str | None = None) -> list[MemoryItem]:
        if project_id:
            rows = self.store.fetchall(
                "SELECT * FROM cb_memory_items WHERE project_id = ? ORDER BY created_at, id",
                (project_id,),
            )
        else:
            rows = self.store.fetchall("SELECT * FROM cb_memory_items ORDER BY created_at, id")
        return self._rows_to_items(rows)

    def preferences(self, project_id: str | None = None) -> list[dict]:
        return [
            item.to_dict()
            for item in self.current(project_id, MemoryKind.USER_INSTRUCTION)
        ]
