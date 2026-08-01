"""Index-to-Runsheet reconciliation.

Deterministic and evidence-first. Matching never uses a model: entries are
linked by document number, then by recording reference, then by normalized party
and date. Once linked, every material field is compared and each disagreement is
emitted as its own row with the two competing values, so a conflict stays a
conflict instead of being silently resolved.

An unreadable source field never becomes a mismatch — it becomes an
``unreadable_source_field`` row routed to human review. Reporting "the index
disagrees with the Runsheet" when the index cell was actually a smudge would be
a fabricated conflict.
"""

from __future__ import annotations

import re

ENTITY_SUFFIXES = (
    "LLC", "L L C", "INC", "INCORPORATED", "CO", "COMPANY", "CORP", "CORPORATION",
    "LP", "L P", "LTD", "PARTNERS", "PARTNERSHIP", "TRUST", "ESTATE",
)

_PUNCTUATION = re.compile(r"[^A-Z0-9 ]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_party(value: str | None) -> str:
    if not value:
        return ""
    upper = _PUNCTUATION.sub(" ", value.upper())
    tokens = [token for token in _WHITESPACE.sub(" ", upper).strip().split(" ") if token]
    while tokens and tokens[-1] in ENTITY_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def normalize_reference(value: str | None) -> str:
    if not value:
        return ""
    digits = re.sub(r"[^0-9A-Za-z]", "", value).upper()
    stripped = digits.lstrip("0")
    return stripped or digits


def normalize_legal(value: str | None) -> str:
    if not value:
        return ""
    upper = _PUNCTUATION.sub(" ", value.upper())
    return _WHITESPACE.sub(" ", upper).strip()


def _field(entry: dict, name: str) -> dict:
    return entry.get("fields", {}).get(name, {"value": None, "state": "absent", "confidence": 0.0})


def _value(entry: dict, name: str):
    return _field(entry, name).get("value")


def _state(entry: dict, name: str) -> str:
    return _field(entry, name).get("state", "absent")


def _row(category, index_entry_id, runsheet_entry_id, evidence, **extra) -> dict:
    row = {
        "category": category,
        "index_entry_id": index_entry_id,
        "runsheet_entry_id": runsheet_entry_id,
        "evidence": evidence,
        "requires_human_review": extra.pop("requires_human_review", False),
    }
    row.update({key: value for key, value in extra.items() if value is not None or key in ("field",)})
    return row


def _link_key(entry: dict) -> tuple:
    """Best available join key for an index entry."""
    document_number = normalize_reference(_value(entry, "document_number"))
    if document_number:
        return ("doc", document_number)
    book = normalize_reference(_value(entry, "book"))
    page = normalize_reference(_value(entry, "page"))
    if book and page:
        return ("bookpage", f"{book}/{page}")
    return (
        "party",
        f"{normalize_party(_value(entry, 'grantor'))}|{normalize_party(_value(entry, 'grantee'))}",
    )


def _runsheet_keys(entry: dict) -> list[tuple]:
    keys = []
    document_number = normalize_reference(entry.get("document_number"))
    if document_number:
        keys.append(("doc", document_number))
    book = normalize_reference(entry.get("book"))
    page = normalize_reference(entry.get("page"))
    if book and page:
        keys.append(("bookpage", f"{book}/{page}"))
    keys.append(
        (
            "party",
            f"{normalize_party(entry.get('grantor'))}|{normalize_party(entry.get('grantee'))}",
        )
    )
    return keys


#: (index field, runsheet field, conflict category, human review needed)
COMPARISONS = (
    ("grantor", "grantor", "conflicting_parties", True),
    ("grantee", "grantee", "conflicting_parties", True),
    ("book", "book", "conflicting_recording_reference", True),
    ("page", "page", "conflicting_recording_reference", True),
    ("document_number", "document_number", "conflicting_recording_reference", True),
    ("recording_date", "recording_date", "conflicting_dates", True),
    ("legal_description", "legal_description", "conflicting_legal_description", True),
    ("instrument_type", "instrument_type", "conflicting_parties", False),
)

_NORMALIZERS = {
    "grantor": normalize_party,
    "grantee": normalize_party,
    "book": normalize_reference,
    "page": normalize_reference,
    "document_number": normalize_reference,
    "legal_description": normalize_legal,
    "instrument_type": normalize_legal,
    "recording_date": lambda value: (value or "").strip(),
}


def reconcile(entries: list[dict], runsheet: dict) -> dict:
    """Return a schema-valid reconciliation of index entries against a Runsheet."""
    runsheet_entries = list(runsheet.get("entries", []))
    lookup: dict[tuple, dict] = {}
    for entry in runsheet_entries:
        for key in _runsheet_keys(entry):
            lookup.setdefault(key, entry)

    rows: list[dict] = []
    matched_runsheet_ids: set[str] = set()
    seen_index_keys: dict[tuple, str] = {}

    for entry in entries:
        index_id = entry["index_entry_id"]

        key = _link_key(entry)
        duplicate_of = seen_index_keys.get(key)
        if duplicate_of and key[0] != "party":
            rows.append(
                _row(
                    "possible_duplicate",
                    index_id,
                    None,
                    f"Shares recording reference {key[1]} with {duplicate_of}.",
                    requires_human_review=True,
                )
            )
        else:
            seen_index_keys[key] = index_id

        unreadable = [
            name
            for name in ("grantor", "grantee", "book", "page", "document_number", "recording_date")
            if _state(entry, name) == "unreadable"
        ]
        for name in unreadable:
            rows.append(
                _row(
                    "unreadable_source_field",
                    index_id,
                    None,
                    f"Source cell for {name} was not legible; no value asserted.",
                    field=name,
                    index_value=None,
                    requires_human_review=True,
                )
            )

        match = None
        match_kind = None
        for candidate_key in (key, ("doc", normalize_reference(_value(entry, "document_number")))):
            if candidate_key in lookup:
                match = lookup[candidate_key]
                match_kind = candidate_key[0]
                break
        if match is None:
            for candidate_key in _runsheet_keys(
                {
                    "grantor": _value(entry, "grantor"),
                    "grantee": _value(entry, "grantee"),
                    "book": _value(entry, "book"),
                    "page": _value(entry, "page"),
                    "document_number": _value(entry, "document_number"),
                }
            ):
                if candidate_key in lookup:
                    match = lookup[candidate_key]
                    match_kind = candidate_key[0]
                    break

        if match is None:
            rows.append(
                _row(
                    "index_only",
                    index_id,
                    None,
                    "No Runsheet entry shares this document number, recording reference, or parties.",
                    requires_human_review=True,
                )
            )
            continue

        matched_runsheet_ids.add(match["runsheet_entry_id"])
        differences = []
        normalized_only = []
        for index_field, runsheet_field, category, needs_review in COMPARISONS:
            state = _state(entry, index_field)
            if state in ("unreadable", "absent", "not_applicable"):
                continue
            index_value = _value(entry, index_field)
            runsheet_value = match.get(runsheet_field)
            if index_value is None or runsheet_value is None:
                continue
            normalizer = _NORMALIZERS.get(index_field, lambda value: value)
            if str(index_value) == str(runsheet_value):
                continue
            if normalizer(index_value) == normalizer(runsheet_value):
                normalized_only.append(index_field)
                continue
            differences.append(
                _row(
                    category,
                    index_id,
                    match["runsheet_entry_id"],
                    f"Index {index_field}={index_value!r} vs Runsheet {runsheet_field}={runsheet_value!r}.",
                    field=index_field,
                    index_value=str(index_value),
                    runsheet_value=str(runsheet_value),
                    requires_human_review=needs_review,
                )
            )

        if differences:
            rows.extend(differences)
            if state_is_uncertain(entry):
                rows.append(
                    _row(
                        "uncertain_chain_link",
                        index_id,
                        match["runsheet_entry_id"],
                        "Linked entry contains uncertain source fields; chain position is not settled.",
                        requires_human_review=True,
                    )
                )
        elif normalized_only:
            rows.append(
                _row(
                    "normalized_match",
                    index_id,
                    match["runsheet_entry_id"],
                    f"Matched after normalizing {', '.join(sorted(normalized_only))}.",
                )
            )
        elif match_kind == "party":
            rows.append(
                _row(
                    "probable_match",
                    index_id,
                    match["runsheet_entry_id"],
                    "Matched on parties only; no shared recording reference.",
                    requires_human_review=True,
                )
            )
        else:
            rows.append(
                _row(
                    "exact_match",
                    index_id,
                    match["runsheet_entry_id"],
                    f"All compared fields agree (linked by {match_kind}).",
                )
            )

    for entry in runsheet_entries:
        if entry["runsheet_entry_id"] not in matched_runsheet_ids:
            rows.append(
                _row(
                    "runsheet_only",
                    None,
                    entry["runsheet_entry_id"],
                    "No index entry supports this Runsheet row.",
                    requires_human_review=True,
                )
            )

    return {"rows": rows}


def state_is_uncertain(entry: dict) -> bool:
    return any(
        field.get("state") == "uncertain" for field in entry.get("fields", {}).values()
    )


def summarize(reconciliation: dict) -> dict:
    counts: dict[str, int] = {}
    for row in reconciliation["rows"]:
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    review = [row for row in reconciliation["rows"] if row.get("requires_human_review")]
    return {
        "counts": dict(sorted(counts.items())),
        "total_rows": len(reconciliation["rows"]),
        "human_review_rows": len(review),
        "coverage": counts.get("exact_match", 0)
        + counts.get("normalized_match", 0)
        + counts.get("probable_match", 0),
    }
