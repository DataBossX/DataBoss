"""SYNTHETIC fixture corpus for the controlled demo.

Everything in this module is invented. No Horizon, Penterra, or other client
material appears here, and nothing here should ever be used as evidence for real
title work. Names, books, pages, and document numbers are fictional and the
legal descriptions describe a fictional county.

The corpus carries **ground truth plus per-field legibility**, which is what
makes objective scoring possible: a scorer can tell the difference between a
reader that correctly reported "unreadable" and one that invented a confident
value for the same smudged cell.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .util import canonical_hash

SYNTHETIC_BANNER = "SYNTHETIC FIXTURE — not client evidence"

CLEAR = "clear"
FAINT = "faint"
ILLEGIBLE = "illegible"
BLANK = "blank"


@dataclass(frozen=True)
class SyntheticField:
    value: str | None
    legibility: str = CLEAR

    def truth_state(self) -> str:
        if self.legibility == BLANK:
            return "absent"
        if self.legibility == ILLEGIBLE:
            return "unreadable"
        return "known"


@dataclass(frozen=True)
class SyntheticRow:
    row: int
    fields: dict
    #: Pixel-ish region used for source-region citations.
    region: dict = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0})


@dataclass(frozen=True)
class SyntheticPage:
    page_id: str
    label: str
    rows: tuple

    def to_dict(self) -> dict:
        return {
            "banner": SYNTHETIC_BANNER,
            "page_id": self.page_id,
            "label": self.label,
            "rows": [
                {
                    "row": row.row,
                    "region": row.region,
                    "fields": {
                        name: {"value": f.value, "legibility": f.legibility}
                        for name, f in row.fields.items()
                    },
                }
                for row in self.rows
            ],
        }


def _row(index: int, **values) -> SyntheticRow:
    fields = {}
    for name, spec in values.items():
        if isinstance(spec, tuple):
            fields[name] = SyntheticField(spec[0], spec[1])
        else:
            fields[name] = SyntheticField(spec, CLEAR)
    return SyntheticRow(
        row=index,
        fields=fields,
        region={"x": 40.0, "y": 100.0 + index * 48.0, "width": 1120.0, "height": 44.0},
    )


BASE_LOCATION = {
    "section": "32",
    "township": "12N",
    "range": "21W",
    "county": "Fictional",
    "state": "OK",
}


def build_index_pages() -> list[SyntheticPage]:
    """Two handwritten-style index pages with deliberate legibility problems."""
    page_one_rows = (
        _row(
            0,
            grantor="ALDER, MARGUERITE T",
            grantee="BRIGHTWATER MINERALS LLC",
            instrument_type="MINERAL DEED",
            recording_date="1974-03-11",
            execution_date="1974-02-28",
            book="0412",
            page="0331",
            document_number="R-1974-0888",
            legal_description="NW/4 SEC 32-12N-21W",
            interest_or_burden="1/2 MINERAL",
            **BASE_LOCATION,
        ),
        _row(
            1,
            grantor="BRIGHTWATER MINERALS LLC",
            grantee=("CALLOWAY, EDMOND R", FAINT),
            instrument_type="MINERAL DEED",
            recording_date="1981-07-02",
            execution_date=(None, ILLEGIBLE),
            book="0553",
            page=("0117", FAINT),
            document_number="R-1981-2041",
            legal_description="NW/4 SEC 32-12N-21W",
            interest_or_burden="1/4 MINERAL",
            **BASE_LOCATION,
        ),
        _row(
            2,
            grantor="CALLOWAY, EDMOND R",
            grantee="DUNLIN OPERATING CO",
            instrument_type="OIL AND GAS LEASE",
            recording_date="1998-11-19",
            execution_date="1998-10-30",
            book=("0891", ILLEGIBLE),
            page=("0044", ILLEGIBLE),
            document_number="R-1998-7712",
            legal_description="NW/4 SEC 32-12N-21W",
            interest_or_burden="LEASEHOLD",
            **BASE_LOCATION,
        ),
        _row(
            3,
            grantor="ALDER, MARGUERITE T",
            grantee="EMBER TRUST",
            instrument_type="QUITCLAIM DEED",
            recording_date="2003-05-06",
            execution_date=(None, BLANK),
            book="1204",
            page="0902",
            document_number="R-2003-3310",
            legal_description="S/2 NE/4 SEC 32-12N-21W",
            interest_or_burden="ALL RIGHT TITLE",
            **BASE_LOCATION,
        ),
    )
    page_two_rows = (
        _row(
            0,
            grantor="DUNLIN OPERATING CO",
            grantee="FARROW ENERGY PARTNERS",
            instrument_type="ASSIGNMENT",
            recording_date="2011-09-14",
            execution_date="2011-08-22",
            book="1688",
            page="0210",
            document_number="R-2011-5540",
            legal_description="NW/4 SEC 32-12N-21W",
            interest_or_burden="LEASEHOLD 100%",
            **BASE_LOCATION,
        ),
        _row(
            1,
            grantor="EMBER TRUST",
            grantee=("GRISWOLD, HANNAH", FAINT),
            instrument_type="MINERAL DEED",
            recording_date=("2016-04-01", FAINT),
            execution_date="2016-03-15",
            book="1902",
            page="0455",
            document_number=(None, ILLEGIBLE),
            legal_description="S/2 NE/4 SEC 32-12N-21W",
            interest_or_burden="1/8 MINERAL",
            **BASE_LOCATION,
        ),
        _row(
            2,
            grantor="FARROW ENERGY PARTNERS",
            grantee="HOLLIS RESOURCES INC",
            instrument_type="ASSIGNMENT",
            recording_date="2019-02-27",
            execution_date="2019-02-01",
            book="2044",
            page="0783",
            document_number="R-2019-1187",
            legal_description="NW/4 SEC 32-12N-21W",
            interest_or_burden="LEASEHOLD 50%",
            **BASE_LOCATION,
        ),
    )
    return [
        SyntheticPage("idx_page_001", "Grantor index, page 1 of 2 (SYNTHETIC)", page_one_rows),
        SyntheticPage("idx_page_002", "Grantor index, page 2 of 2 (SYNTHETIC)", page_two_rows),
    ]


def build_runsheet() -> dict:
    """A synthetic Runsheet that deliberately disagrees with the index in places.

    The disagreements are the point: a reconciliation that reports zero conflicts
    against this fixture is broken, not clean.
    """
    return {
        "banner": SYNTHETIC_BANNER,
        "runsheet_id": "runsheet_sec32_synthetic",
        "entries": [
            {
                "runsheet_entry_id": "rs_001",
                "grantor": "ALDER, MARGUERITE T",
                "grantee": "BRIGHTWATER MINERALS LLC",
                "instrument_type": "MINERAL DEED",
                "recording_date": "1974-03-11",
                "book": "0412",
                "page": "0331",
                "document_number": "R-1974-0888",
                "legal_description": "NW/4 SEC 32-12N-21W",
            },
            {
                # Party spelled differently: normalized match, not exact.
                "runsheet_entry_id": "rs_002",
                "grantor": "Brightwater Minerals, L.L.C.",
                "grantee": "CALLOWAY, EDMOND R.",
                "instrument_type": "MINERAL DEED",
                "recording_date": "1981-07-02",
                "book": "0553",
                "page": "0117",
                "document_number": "R-1981-2041",
                "legal_description": "NW/4 SEC 32-12N-21W",
            },
            {
                # Recording reference conflict: Runsheet says 0891/0045.
                "runsheet_entry_id": "rs_003",
                "grantor": "CALLOWAY, EDMOND R",
                "grantee": "DUNLIN OPERATING CO",
                "instrument_type": "OIL AND GAS LEASE",
                "recording_date": "1998-11-19",
                "book": "0891",
                "page": "0045",
                "document_number": "R-1998-7712",
                "legal_description": "NW/4 SEC 32-12N-21W",
            },
            {
                # Legal description conflict against the index.
                "runsheet_entry_id": "rs_004",
                "grantor": "ALDER, MARGUERITE T",
                "grantee": "EMBER TRUST",
                "instrument_type": "QUITCLAIM DEED",
                "recording_date": "2003-05-06",
                "book": "1204",
                "page": "0902",
                "document_number": "R-2003-3310",
                "legal_description": "N/2 NE/4 SEC 32-12N-21W",
            },
            {
                "runsheet_entry_id": "rs_005",
                "grantor": "DUNLIN OPERATING CO",
                "grantee": "FARROW ENERGY PARTNERS",
                "instrument_type": "ASSIGNMENT",
                "recording_date": "2011-09-14",
                "book": "1688",
                "page": "0210",
                "document_number": "R-2011-5540",
                "legal_description": "NW/4 SEC 32-12N-21W",
            },
            {
                # Present only on the Runsheet: no index row supports it.
                "runsheet_entry_id": "rs_006",
                "grantor": "HOLLIS RESOURCES INC",
                "grantee": "IRONVALE MIDSTREAM LLC",
                "instrument_type": "RIGHT OF WAY",
                "recording_date": "2021-06-30",
                "book": "2210",
                "page": "0099",
                "document_number": "R-2021-4402",
                "legal_description": "NW/4 SEC 32-12N-21W",
            },
        ],
    }


def ground_truth(pages) -> dict:
    """``{(page_id, row, field): (value, truth_state)}`` for objective scoring."""
    truth = {}
    for page in pages:
        for row in page.rows:
            for name, synthetic_field in row.fields.items():
                truth[(page.page_id, row.row, name)] = (
                    synthetic_field.value,
                    synthetic_field.truth_state(),
                )
    return truth


@dataclass(frozen=True)
class SyntheticCorpus:
    pages: tuple
    runsheet: dict

    @property
    def truth(self) -> dict:
        return ground_truth(self.pages)

    def page(self, page_id: str) -> SyntheticPage:
        for page in self.pages:
            if page.page_id == page_id:
                return page
        raise KeyError(page_id)

    def page_hash(self, page_id: str) -> str:
        return canonical_hash(self.page(page_id).to_dict())

    def runsheet_hash(self) -> str:
        return canonical_hash(self.runsheet)

    def to_dict(self) -> dict:
        return {
            "banner": SYNTHETIC_BANNER,
            "pages": [page.to_dict() for page in self.pages],
            "runsheet": self.runsheet,
        }


def build_corpus() -> SyntheticCorpus:
    return SyntheticCorpus(pages=tuple(build_index_pages()), runsheet=build_runsheet())
