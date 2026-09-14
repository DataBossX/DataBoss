"""Blank classification. UNKNOWN is never zero, and a blank is never invented away."""
from __future__ import annotations

INTENTIONAL = "INTENTIONAL"    # house convention leaves this blank for this doc type
INAPPLICABLE = "INAPPLICABLE"  # the field cannot exist on this instrument
SOURCE_MISSING = "SOURCE_MISSING"  # no source PDF/face is in custody
UNREADABLE = "UNREADABLE"      # face is in custody but the field cannot be read
TRUE_HOLD = "TRUE_HOLD"        # face read, value genuinely indeterminate
CLASSES = (INTENTIONAL, INAPPLICABLE, SOURCE_MISSING, UNREADABLE, TRUE_HOLD)

# Instrument types that legitimately carry no conveyancing parties.
_NO_PARTY_TYPES = {"corner record", "master title plat", "dependent resurvey plat",
                   "case abstract", "notice of filing of plats of survey"}
# Types whose collateral is general, so a Section legal is not expected.
_NO_LEGAL_TYPES = {"ucc financing statement", "financing statement",
                   "ucc financing statement amendment", "ucc financing statement termination",
                   "ucc financing statement continuation", "termination",
                   "release of lien", "partial release of lien",
                   "release of mortgage", "release of oil and gas mortgage",
                   "security agreement and financing statement",
                   "notice of successor agent", "transfer of note"}
# Modern Campbell filings are doc-number-only: no book/page exists to record.
_DOCNO_ONLY_PREFIXES = tuple(f"{y}-" for y in range(2000, 2031))


def classify(field: str, doc_type: str | None, *, docno: str = "",
             has_source: bool = True, face_read: bool = True,
             legible: bool = True) -> tuple[str, str]:
    """Return (class, reason) for one blank cell. Never returns a value."""
    f = (field or "").strip().lower()
    t = (doc_type or "").strip().lower()

    if f in {"book-page", "book/page", "bookpage"} and str(docno).startswith(_DOCNO_ONLY_PREFIXES):
        return INAPPLICABLE, "modern doc-number-only recording; no book/page exists on the face"
    if f in {"grantor", "grantee"} and t in _NO_PARTY_TYPES:
        return INAPPLICABLE, f"'{doc_type}' is a statutory/administrative filing with no conveyancing parties"
    if f in {"legal description", "legal"} and t in _NO_LEGAL_TYPES:
        return INTENTIONAL, f"house convention: '{doc_type}' describes general collateral, not Section lands"
    if not has_source:
        return SOURCE_MISSING, "no source face is in custody for this identity"
    if not face_read:
        return SOURCE_MISSING, "source is in custody but the decisive page was not opened"
    if not legible:
        return UNREADABLE, "face is in custody but the field is illegible"
    return TRUE_HOLD, "face read; value genuinely indeterminate on the source"


def census(cells: list[dict]) -> dict:
    """cells = [{field, doc_type, docno, has_source, face_read, legible}]"""
    out = {c: [] for c in CLASSES}
    for c in cells:
        klass, reason = classify(
            c.get("field", ""), c.get("doc_type"), docno=c.get("docno", ""),
            has_source=c.get("has_source", True), face_read=c.get("face_read", True),
            legible=c.get("legible", True))
        out[klass].append({**c, "reason": reason})
    return {"counts": {k: len(v) for k, v in out.items()},
            "total": len(cells), "detail": out}
