"""Data models for the landman report pipeline."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional

JobSource = Literal["wyoming", "oklahoma"]
JobStatus = Literal[
    "queued", "ingesting", "ocr", "extracting", "reasoning", "reporting", "done", "failed"
]


@dataclass
class Instrument:
    doc_no: Optional[str] = None
    instrument_type: Optional[str] = None
    book: Optional[str] = None
    page: Optional[str] = None
    recording_date: Optional[str] = None
    instrument_date: Optional[str] = None
    grantors: list[str] = field(default_factory=list)
    grantees: list[str] = field(default_factory=list)
    legal_description: Optional[str] = None
    section: Optional[str] = None
    township: Optional[str] = None
    range_val: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None
    interest_conveyed: Optional[str] = None
    lease_royalty_terms: Optional[str] = None
    consideration: Optional[str] = None
    reservations: Optional[str] = None
    notes: Optional[str] = None
    confidence_score: float = 0.0
    needs_review: bool = False
    source_file: Optional[str] = None
    source_url: Optional[str] = None
    raw_ocr_text: Optional[str] = None
    ocr_method: Optional[str] = None
    extract_cost: float = 0.0

    def to_dict(self) -> dict:
        return {
            "doc_no": self.doc_no,
            "instrument_type": self.instrument_type,
            "book": self.book,
            "page": self.page,
            "recording_date": self.recording_date,
            "instrument_date": self.instrument_date,
            "grantors": self.grantors,
            "grantees": self.grantees,
            "legal_description": self.legal_description,
            "section": self.section,
            "township": self.township,
            "range_val": self.range_val,
            "county": self.county,
            "state": self.state,
            "interest_conveyed": self.interest_conveyed,
            "lease_royalty_terms": self.lease_royalty_terms,
            "consideration": self.consideration,
            "reservations": self.reservations,
            "notes": self.notes,
            "confidence_score": self.confidence_score,
            "needs_review": self.needs_review,
            "source_file": self.source_file,
            "source_url": self.source_url,
            "ocr_method": self.ocr_method,
            "extract_cost": self.extract_cost,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Instrument":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ChainLink:
    link_no: int = 0
    doc_no: Optional[str] = None
    instrument_type: Optional[str] = None
    recording_date: Optional[str] = None
    from_parties: list[str] = field(default_factory=list)
    to_parties: list[str] = field(default_factory=list)
    interest_conveyed: Optional[str] = None
    fraction: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "link_no": self.link_no,
            "doc_no": self.doc_no,
            "instrument_type": self.instrument_type,
            "recording_date": self.recording_date,
            "from": self.from_parties,
            "to": self.to_parties,
            "interest_conveyed": self.interest_conveyed,
            "fraction": self.fraction,
        }


@dataclass
class ChainOfTitle:
    chain: list[ChainLink] = field(default_factory=list)
    current_owners: list[dict] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    encumbrances: list[str] = field(default_factory=list)
    curative_needed: list[str] = field(default_factory=list)
    status: str = "Unknown—needs manual"
    confidence: float = 0.0
    explanation: Optional[str] = None
    title_opinion_notes: Optional[str] = None
    reasoning_method: str = "rule_based"
    reasoning_cost: float = 0.0

    def to_dict(self) -> dict:
        return {
            "chain": [c.to_dict() for c in self.chain],
            "current_owners": self.current_owners,
            "gaps": self.gaps,
            "encumbrances": self.encumbrances,
            "curative_needed": self.curative_needed,
            "status": self.status,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "title_opinion_notes": self.title_opinion_notes,
            "reasoning_method": self.reasoning_method,
            "reasoning_cost": self.reasoning_cost,
        }


@dataclass
class StageEvent:
    stage: str
    message: str
    cost: float = 0.0
    ts: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {"stage": self.stage, "message": self.message, "cost": self.cost, "ts": self.ts}


@dataclass
class Job:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: JobSource = "oklahoma"
    status: JobStatus = "queued"

    # Input
    files: list[str] = field(default_factory=list)
    pull_list_batch_id: Optional[str] = None
    tract_description: Optional[str] = None
    owner_name: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None

    # Stage outputs
    ingested_files: list[str] = field(default_factory=list)
    ocr_results: list[dict] = field(default_factory=list)
    instruments: list[Instrument] = field(default_factory=list)
    chain: Optional[ChainOfTitle] = None
    report_path: Optional[str] = None
    report_json: Optional[dict] = None

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    error: Optional[str] = None
    total_cost: float = 0.0
    stage_log: list[StageEvent] = field(default_factory=list)

    def log(self, stage: str, msg: str, cost: float = 0.0) -> None:
        self.stage_log.append(StageEvent(stage=stage, message=msg, cost=cost))
        self.total_cost += cost
        self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "status": self.status,
            "files": self.files,
            "pull_list_batch_id": self.pull_list_batch_id,
            "tract_description": self.tract_description,
            "owner_name": self.owner_name,
            "county": self.county,
            "state": self.state,
            "ingested_files": self.ingested_files,
            "ocr_results": self.ocr_results,
            "instruments": [i.to_dict() for i in self.instruments],
            "chain": self.chain.to_dict() if self.chain else None,
            "report_path": self.report_path,
            "report_json": self.report_json,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
            "total_cost": self.total_cost,
            "stage_log": [e.to_dict() for e in self.stage_log],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        instruments = [Instrument.from_dict(i) for i in d.get("instruments", [])]
        chain_data = d.get("chain")
        chain = None
        if chain_data:
            chain = ChainOfTitle(
                chain=[ChainLink(**{k if k != "from" else "from_parties": v
                                   for k, v in link.items()
                                   if k in ("link_no", "doc_no", "instrument_type",
                                            "recording_date", "fraction", "interest_conveyed")
                                   or k == "from" or k == "to"}
                                 ) for link in chain_data.get("chain", [])],
                current_owners=chain_data.get("current_owners", []),
                gaps=chain_data.get("gaps", []),
                encumbrances=chain_data.get("encumbrances", []),
                curative_needed=chain_data.get("curative_needed", []),
                status=chain_data.get("status", "Unknown—needs manual"),
                confidence=chain_data.get("confidence", 0.0),
                explanation=chain_data.get("explanation"),
                title_opinion_notes=chain_data.get("title_opinion_notes"),
                reasoning_method=chain_data.get("reasoning_method", "rule_based"),
                reasoning_cost=chain_data.get("reasoning_cost", 0.0),
            )
        stage_log = [StageEvent(**e) for e in d.get("stage_log", [])]
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            source=d.get("source", "oklahoma"),
            status=d.get("status", "queued"),
            files=d.get("files", []),
            pull_list_batch_id=d.get("pull_list_batch_id"),
            tract_description=d.get("tract_description"),
            owner_name=d.get("owner_name"),
            county=d.get("county"),
            state=d.get("state"),
            ingested_files=d.get("ingested_files", []),
            ocr_results=d.get("ocr_results", []),
            instruments=instruments,
            chain=chain,
            report_path=d.get("report_path"),
            report_json=d.get("report_json"),
            created_at=d.get("created_at", datetime.utcnow().isoformat()),
            updated_at=d.get("updated_at", datetime.utcnow().isoformat()),
            error=d.get("error"),
            total_cost=d.get("total_cost", 0.0),
            stage_log=stage_log,
        )
