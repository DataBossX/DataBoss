"""Glue: turn a vetted DocExtraction into a RunsheetWrite for a given row.

Applies QA, places flags into Review (T) / NEED-ACTION (U), and builds the
HYPERLINK for the Document Link column. Writes nothing itself — it returns a
RunsheetWrite that the Excel writer consumes on user approval.
"""
from __future__ import annotations

from .schemas import DocExtraction, RunsheetWrite
from .qa.engine import qa_extraction


def to_runsheet_write(ext: DocExtraction, row: int) -> tuple[RunsheetWrite, dict]:
    qa = qa_extraction(ext)

    values: dict[str, object] = {}

    def put(field, value):
        if value is not None and value != "":
            values[field] = value

    put("instrument_number", ext.instrument_number)
    put("doc_type", ext.doc_type or ext.doc_type_original)
    put("book_page", ext.book_page)
    put("effective_date", ext.effective_date)
    put("recorded_date", ext.recorded_date)
    put("grantor", ext.grantor)
    put("grantee", ext.grantee)
    put("legal_description", ext.legal_description)
    put("tracts", ext.tracts)
    put("conveyance_type", ext.conveyance_type or ext.classification)
    put("conveyance_amount_dec", ext.conveyance_amount_dec)

    # Notes: keep original doc-type wording + model notes (no evidence lost)
    note_bits = []
    if ext.doc_type_original and ext.doc_type_original != ext.doc_type:
        note_bits.append(f"src doctype: {ext.doc_type_original}")
    if ext.notes:
        note_bits.append(ext.notes)
    if note_bits:
        values["notes"] = " | ".join(note_bits)

    # Review (T) and NEED/ACTION (U) carry uncertainty — never silent.
    if qa["review"]:
        values["review"] = qa["review"]
    if qa["need"]:
        values["need_action"] = qa["need"]

    rw = RunsheetWrite(
        row=row,
        values=values,
        document_link_url=ext.document_link,
        document_link_label=ext.book_page or ext.instrument_number or "Document",
    )
    return rw, qa
