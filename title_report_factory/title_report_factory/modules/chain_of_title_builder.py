"""chain_of_title_builder -- assemble the apparent Diversified chain of title.

Reads the curated interest chain plus the FourPoint (Track A) and DP Legacy
(Track B) supporting sheets, and emits ordered, confidence-scored ChainLinks.
"""
from __future__ import annotations

from ..model import ChainLink
from . import source_reader
from .party_and_date_extractor import to_short_date, grantor_grantee
from .document_classifier import classify
from .interest_extractor import interest_type


def _flag_confidence(flag: str, doc_class: str) -> tuple[int, str]:
    f = (flag or "").lower()
    if "direct diversified" in f:
        base, label = 60, "Index record; title effect unverified"
    elif "predecessor" in f:
        base, label = 55, "Predecessor index record; unverified"
    elif "divestiture" in f or "exclusion" in f:
        base, label = 45, "Possible divestiture/exclusion; schedule controls"
    elif "encumbrance" in f or "lien" in f:
        base, label = 50, "Encumbrance/lien track; index only"
    elif "support" in f or "identity" in f or "related" in f:
        base, label = 45, "Support/identity record only"
    else:
        base, label = 50, "Index only"
    # affidavits/agreements/mergers are weaker title proof
    if doc_class in {"Affidavit", "Agreement", "Memorandum", "Merger"}:
        base -= 5
    return max(base, 25), label


def build_chain(path: str, sheet_map: dict, subject: dict) -> list[ChainLink]:
    links: list[ChainLink] = []

    # 1) Curated interest chain (diversifiedint)
    rows = source_reader.as_dicts(source_reader.read_sheet(path, sheet_map["diversified_interest"]))
    for d in rows:
        parties = d.get("Parties", "")
        grantor, grantee = grantor_grantee(parties)
        doc_type = str(d.get("Doc Type", "") or "").strip()
        cls, _ = classify(doc_type)
        flag = str(d.get("Interest Flag", "") or "")
        conf, label = _flag_confidence(flag, cls)
        links.append(ChainLink(
            date=to_short_date(d.get("Recorded Date")),
            instrument_no=str(d.get("Instrument", "") or "").strip(),
            doc_type=cls or doc_type,
            book_page=str(d.get("Bk/Pg.", "") or "").strip(),
            grantor=grantor, grantee=grantee,
            legal_scope=subject_str(subject),
            chain_function=str(d.get("Effect / Next Move", "") or "").strip(),
            interest_affected=interest_type(cls, doc_type),
            confidence_label=label, confidence=conf,
            limitations="Recorded image/lease schedule not reviewed; net acres, depths, "
                        "burdens and exclusions unverified.",
            source=str(d.get("Detail Link", "") or "diversifiedint"),
            track=_track_of(flag),
        ))

    # 2) Corporate-succession support (FourPoint -> Maverick -> Diversified)
    fp = source_reader.as_dicts(source_reader.read_sheet(path, sheet_map["chain_fourpoint"]))
    for d in fp:
        st = str(d.get("Source Type", "") or "")
        if "corporate" not in st.lower():
            continue  # county records already captured above
        links.append(ChainLink(
            date=to_short_date(d.get("Date")),
            instrument_no=str(d.get("Instrument / Source", "") or "").strip(),
            doc_type="Corporate Succession (public source)",
            book_page="N/A",
            grantor=str(d.get("Grantor / From", "") or "").strip(),
            grantee=str(d.get("Grantee / To", "") or "").strip(),
            legal_scope="Corporate-level; no county legal/schedule",
            chain_function=str(d.get("Chain Function", "") or "").strip(),
            interest_affected="Corporate succession (entity-level)",
            confidence_label="High for public corporate event; not county title proof",
            confidence=55,
            limitations=str(d.get("Limitations", "") or "").strip(),
            source=str(d.get("Instrument / Source", "") or "Public corporate source"),
            track="A - FourPoint/Maverick/Diversified",
        ))

    links.sort(key=lambda x: _date_key(x.date))
    return links


def subject_str(subject: dict) -> str:
    return f"{subject['section']}-{subject['township']}-{subject['range']}"


def _track_of(flag: str) -> str:
    f = (flag or "").lower()
    if "predecessor" in f:
        return "Predecessor"
    if "divestiture" in f or "exclusion" in f:
        return "B - Possible exclusion"
    if "encumbrance" in f or "lien" in f:
        return "Encumbrance"
    if "direct" in f:
        return "B - DP Legacy/Diversified"
    return "Support"


def _date_key(s: str):
    try:
        m, d, y = (int(x) for x in s.split("/"))
        return (y, m, d)
    except Exception:
        return (9999, 99, 99)
