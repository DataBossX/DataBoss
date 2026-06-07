"""index_builder -- consolidate every known instrument into a full-text index.

Sources merged (deduplicated by instrument no / book-page):
  * 64 base oil & gas leases (OGL sheet)
  * the curated Diversified interest chain (diversifiedint)
  * supporting/curative instruments (inst sheet)

Each row is classified, given title relevance, and carries match / OCR /
relevance confidence scores. Name-match-trap entities are flagged, not assumed.
"""
from __future__ import annotations

from ..model import Instrument, Lease, ChainLink
from . import source_reader
from .document_classifier import classify
from .party_and_date_extractor import to_short_date, grantor_grantee
from .interest_extractor import interest_type
from .legal_description_extractor import matches_subject


def _norm_key(instrument_no: str, book_page: str) -> str:
    return (instrument_no or "").strip() or (book_page or "").strip()


def build_index(path: str, sheet_map: dict, leases: list[Lease], chain: list[ChainLink],
                subject: dict, name_traps: list[str]) -> list[Instrument]:
    rows: list[Instrument] = []
    seen: set[str] = set()
    n = 0

    # --- 1) Base oil & gas leases -----------------------------------------
    for lz in leases:
        cls, cat = classify("Oil and Gas Lease", lz.notes)
        key = _norm_key(lz.instrument_no, lz.book_page)
        if key in seen:
            continue
        seen.add(key)
        n += 1
        ocr_conf = 60 if "first-page" in (lz.data_status or "").lower() else 30
        rows.append(Instrument(
            index_no=n, source_file=lz.source_file, matched_document=f"OGL {lz.ogl_no}",
            doc_type=cls, instrument_no=lz.instrument_no, book_page=lz.book_page,
            recording_date=lz.filing_date, execution_date=lz.execution_date, effective_date=lz.execution_date,
            grantor=lz.grantor, grantee=lz.grantee, legal_description=lz.legal_description,
            interest=interest_type(cls), lease_terms=lz.term, royalty=lz.royalty,
            gross_acres=lz.gross_acres, net_acres=lz.net_acres or "Not Verified",
            notes=lz.notes or "Index/first-page only; full lease not abstracted.",
            title_effect=cat, source_reference=lz.source_file or "OGL sheet",
            ocr_confidence=ocr_conf, match_confidence=lz.confidence,
            relevance_confidence=85, classification=cls, track="Base OGL",
        ))

    # --- 2) Curated Diversified chain instruments -------------------------
    for cl in chain:
        key = _norm_key(cl.instrument_no, cl.book_page)
        if not key or key in seen:
            continue
        seen.add(key)
        n += 1
        trap = any(t.lower() in (cl.grantor + cl.grantee).lower() for t in name_traps)
        note = cl.chain_function
        if trap:
            note = "NAME-MATCH TRAP: unrelated 'Diversified Financial' entity, not the subject " \
                   "Diversified Production/Energy. Excluded from mineral chain. " + note
        rows.append(Instrument(
            index_no=n, source_file="diversifiedint", matched_document=cl.doc_type,
            doc_type=cl.doc_type, instrument_no=cl.instrument_no, book_page=cl.book_page,
            recording_date=cl.date, execution_date="", effective_date="",
            grantor=cl.grantor, grantee=cl.grantee, legal_description=cl.legal_scope,
            interest=cl.interest_affected, lease_terms="Not Applicable", royalty="Not Applicable",
            gross_acres="Needs Review", net_acres="Needs Review", notes=note,
            title_effect=cl.confidence_label, source_reference=cl.source,
            ocr_confidence=0, match_confidence=cl.confidence,
            relevance_confidence=(20 if trap else 70), classification=cl.doc_type, track=cl.track,
        ))

    # --- 3) Supporting / curative instruments (inst sheet) ----------------
    for d in source_reader.as_dicts(source_reader.read_sheet(path, sheet_map["instrument_tracking"])):
        instrument_no = str(d.get("Instrument", "") or "").strip()
        book_page = str(d.get("Book/Page", "") or "").strip()
        key = _norm_key(instrument_no, book_page)
        if not key or key in seen:
            continue
        # skip the aggregate lease-group rows already represented by OGL leases
        if "through" in instrument_no.lower():
            continue
        seen.add(key)
        n += 1
        doc_type = str(d.get("Doc Type", "") or "").strip()
        cls, cat = classify(doc_type)
        parties = str(d.get("Parties", "") or "")
        grantor, grantee = grantor_grantee(parties)
        rows.append(Instrument(
            index_no=n, source_file="inst", matched_document=cls, doc_type=cls,
            instrument_no=instrument_no, book_page=book_page,
            recording_date=to_short_date(d.get("Recorded Date")),
            grantor=grantor or parties, grantee=grantee,
            legal_description=f"{subject['section']}-{subject['township']}-{subject['range']}",
            interest=interest_type(cls, doc_type),
            lease_terms="Not Applicable", royalty="Not Applicable",
            gross_acres="Needs Review", net_acres="Needs Review",
            notes=str(d.get("Report Effect", "") or ""), title_effect=cat,
            source_reference=str(d.get("Status / Next Step", "") or "inst sheet"),
            ocr_confidence=0, match_confidence=55, relevance_confidence=65,
            classification=cls, track=str(d.get("Track/Type", "") or ""),
        ))

    return rows
