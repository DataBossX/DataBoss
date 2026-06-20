"""OK County records client stub.

Mirrors the contract of the production client in
``doto_image_commander/api/okcounty.py`` (cost estimation + approval gating)
but returns deterministic fixtures so the swarm boots and self-tests with no
network and no spend. Swap ``LIVE`` to True (and provide a key) to hit the API.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from evoswarm.settings import settings

STRICT = ConfigDict(strict=True, extra="forbid")


class SearchResult(BaseModel):
    model_config = STRICT
    document_id: str
    county: str
    book: str
    page: str
    instrument_type: str
    recording_date: str
    estimated_cost: float = Field(ge=0)


class OKCountyStub:
    """Deterministic stub. estimate_batch_cost matches the live client's shape."""

    LIVE = False

    def is_configured(self) -> bool:
        return bool(settings.okcounty_api_key)

    def estimate_batch_cost(self, n_images: int, n_searches: int = 0) -> dict:
        image_cost = n_images * settings.okcounty_cost_per_image
        search_cost = n_searches * settings.okcounty_cost_per_search
        return {
            "images": n_images,
            "searches": n_searches,
            "image_cost": image_cost,
            "search_cost": search_cost,
            "total": round(image_cost + search_cost, 2),
        }

    def search_document(self, county: str, book: str = "", page: str = "",
                        instrument_type: str = "MINERAL DEED") -> SearchResult:
        if self.LIVE and self.is_configured():  # pragma: no cover - network path
            from doto_image_commander.api.okcounty import client as live  # type: ignore
            r = live.search_document(county, book=book, page=page,
                                     instrument_type=instrument_type)
            if r is None:
                raise LookupError("no document found")
            return SearchResult(
                document_id=r.document_id, county=r.county, book=r.book,
                page=r.page, instrument_type=r.instrument_type,
                recording_date=r.recording_date, estimated_cost=r.estimated_cost,
            )
        return SearchResult(
            document_id=f"STUB-{county}-{book or '0000'}-{page or '000'}",
            county=county, book=book or "5421", page=page or "118",
            instrument_type=instrument_type, recording_date="2026-03-14",
            estimated_cost=settings.okcounty_cost_per_image,
        )


client = OKCountyStub()
