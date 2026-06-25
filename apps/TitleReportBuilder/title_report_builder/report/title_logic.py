"""Title logic: normalize aliquots, map instruments to tracts, build chains.

Never invents. Records carrying an `uncertain` flag (e.g. illegible handwritten
index rows) are kept in a separate, clearly-labeled layer and never promoted to
fact."""
from __future__ import annotations
import re
from dataclasses import dataclass, field

QUARTERS = ("NE", "NW", "SE", "SW")


def normalize_aliquot(s: str | None) -> str | None:
    """'SW/4 of NE/4' / 'sw ne' -> 'SW NE'. Returns None if not a clean 40."""
    if not s:
        return None
    s = s.upper().replace("/4", "").replace("/", " ").replace(".", " ")
    toks = [t for t in re.split(r"\s+", s) if t in QUARTERS]
    if len(toks) >= 2:
        return f"{toks[0]} {toks[1]}"
    return None


def normalize_bookpage(s) -> str:
    if not s:
        return ""
    m = re.search(r"(\d{1,6})\s*/\s*(\d{1,4})", str(s).replace(" ", ""))
    return f"{int(m.group(1))}/{int(m.group(2))}" if m else ""


@dataclass
class Instrument:
    page: int | None = None
    doc_number: str = ""
    date: str = ""
    grantor: str = ""
    grantee: str = ""
    doc_type: str = ""
    aliquots: list[str] = field(default_factory=list)
    legal_text: str = ""
    book_page: str = ""
    acres: object = None
    remarks: str = ""
    uncertain: bool = False
    tracts: list[int] = field(default_factory=list)

    @classmethod
    def from_record(cls, r: dict) -> "Instrument":
        return cls(
            page=r.get("page"),
            doc_number=str(r.get("doc_number") or ""),
            date=str(r.get("rec_date") or r.get("date") or ""),
            grantor=str(r.get("grantor") or ""),
            grantee=str(r.get("grantee") or ""),
            doc_type=str(r.get("doc_type") or ""),
            aliquots=[a for a in (r.get("aliquots") or [])],
            legal_text=str(r.get("legal_text") or ""),
            book_page=normalize_bookpage(r.get("book_page")),
            acres=r.get("acres"),
            remarks=str(r.get("remarks") or ""),
            uncertain=bool(r.get("uncertain")),
        )


def assign_tracts(insts: list[Instrument], aliquot_to_tract: dict[str, int]) -> None:
    for it in insts:
        ts = set()
        for a in it.aliquots:
            na = normalize_aliquot(a)
            if na in aliquot_to_tract:
                ts.add(aliquot_to_tract[na])
        it.tracts = sorted(ts)


def dedupe(insts: list[Instrument]) -> list[Instrument]:
    seen: dict[tuple, Instrument] = {}
    for it in insts:
        key = (it.book_page, it.grantor.upper()[:30], it.grantee.upper()[:30], it.doc_number)
        if key in seen:
            seen[key].tracts = sorted(set(seen[key].tracts) | set(it.tracts))
        else:
            seen[key] = it
    return list(seen.values())


def chains_by_tract(insts: list[Instrument]) -> dict[int, list[Instrument]]:
    out: dict[int, list[Instrument]] = {}
    for it in insts:
        for t in it.tracts:
            out.setdefault(t, []).append(it)
    for t in out:
        out[t].sort(key=lambda x: x.date or "")
    return out
