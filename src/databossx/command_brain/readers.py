"""Simulated index readers used as tournament candidates.

These are **labelled simulations**, not OCR. They exist so the tournament,
scoring, judge, and improvement loop can be exercised end to end on synthetic
data with no cloud call, no client evidence, and a known right answer.

Each profile models a distinct failure mode a real reader can have:

``careful``       reads well, degrades gracefully, admits unreadable cells
``conservative``  high precision, low coverage — marks doubtful cells uncertain
``fabricating``   confidently invents values for cells it cannot read
``transposing``   accurate prose, but transposes digits in recording references

Every value is derived deterministically from the page content and the profile
name, so a given profile produces byte-identical output on every run.
"""

from __future__ import annotations

from dataclasses import dataclass

from .synthetic import BLANK, CLEAR, FAINT, ILLEGIBLE, SyntheticPage
from .util import stable_unit_interval

NUMERIC_FIELDS = ("book", "page", "document_number")


@dataclass(frozen=True)
class ReaderProfile:
    profile_id: str
    description: str
    #: Probability-like thresholds, compared against a deterministic hash.
    fabricates_unreadable: bool = False
    downgrades_faint: bool = False
    transposes_digits: bool = False
    faint_error_rate: float = 0.0
    overconfidence: float = 0.0
    #: Share of otherwise-legible cells this reader declines to commit to.
    omission_rate: float = 0.0


PROFILES = {
    "careful": ReaderProfile(
        "careful",
        "Reads clear text accurately, offers alternatives on faint text, reports unreadable cells.",
        faint_error_rate=0.15,
    ),
    "conservative": ReaderProfile(
        "conservative",
        "High precision, lower coverage: marks doubtful cells uncertain rather than committing.",
        downgrades_faint=True,
        faint_error_rate=0.05,
        omission_rate=0.14,
    ),
    "fabricating": ReaderProfile(
        "fabricating",
        "Invents confident values for cells it cannot read. Included to prove the scorer catches it.",
        fabricates_unreadable=True,
        faint_error_rate=0.45,
        overconfidence=0.35,
    ),
    "transposing": ReaderProfile(
        "transposing",
        "Accurate on prose, transposes digits in book/page references.",
        transposes_digits=True,
        faint_error_rate=0.2,
    ),
}


def _fabricated_value(profile_id: str, page_id: str, row: int, field_name: str) -> str:
    """A plausible-looking invention. Deliberately wrong, deliberately confident."""
    seed = stable_unit_interval(profile_id, page_id, str(row), field_name, "fabricate")
    digits = int(seed * 10_000)
    if field_name in ("book", "page"):
        return f"{digits % 10000:04d}"
    if field_name == "document_number":
        return f"R-19{60 + digits % 40}-{digits % 10000:04d}"
    if field_name in ("recording_date", "execution_date"):
        year = 1960 + digits % 60
        return f"{year}-{1 + digits % 12:02d}-{1 + digits % 28:02d}"
    return f"UNVERIFIED ENTRY {digits % 1000}"


def _transpose(value: str) -> str:
    if value is None or len(value) < 2:
        return value
    chars = list(value)
    for index in range(len(chars) - 1):
        if chars[index].isdigit() and chars[index + 1].isdigit():
            chars[index], chars[index + 1] = chars[index + 1], chars[index]
            break
    return "".join(chars)


def _misread(value: str, profile_id: str, page_id: str, row: int, name: str) -> str:
    """A wrong-but-plausible reading of a faint cell."""
    if value is None:
        return value
    seed = stable_unit_interval(profile_id, page_id, str(row), name, "misread")
    if any(char.isdigit() for char in value):
        return _transpose(value)
    words = value.split()
    if len(words) > 1 and seed > 0.5:
        return " ".join(words[:-1] + [words[-1][:-1] or words[-1]])
    return value.replace("A", "4", 1) if "A" in value else value + "."


def _field(value, state, confidence, region, alternatives=None) -> dict:
    payload = {
        "value": value,
        "state": state,
        "confidence": round(min(max(confidence, 0.0), 1.0), 3),
        "source_region": region,
    }
    if alternatives:
        payload["alternatives"] = list(alternatives)
    return payload


def read_page(profile_id: str, page: SyntheticPage) -> list[dict]:
    """Produce schema-valid index entries for one page under one profile."""
    profile = PROFILES[profile_id]
    entries = []
    for row in page.rows:
        region = {"page_id": page.page_id, "region": dict(row.region), "row": row.row}
        fields = {}
        for name, synthetic_field in row.fields.items():
            value = synthetic_field.value
            legibility = synthetic_field.legibility
            noise = stable_unit_interval(profile_id, page.page_id, str(row.row), name)

            if legibility == CLEAR:
                if profile.omission_rate and noise < profile.omission_rate:
                    # Declines to commit even though the cell is legible. Costs
                    # coverage, which is exactly what a better reader improves on.
                    fields[name] = _field(None, "uncertain", 0.4, region)
                elif profile.transposes_digits and name in NUMERIC_FIELDS and noise < 0.3:
                    fields[name] = _field(_transpose(value), "known", 0.9, region)
                else:
                    fields[name] = _field(value, "known", 0.97 - 0.05 * noise, region)

            elif legibility == FAINT:
                if profile.downgrades_faint:
                    fields[name] = _field(
                        value if noise > profile.faint_error_rate else None,
                        "uncertain",
                        0.45 + 0.1 * noise,
                        region,
                        alternatives=[value] if value else None,
                    )
                elif noise < profile.faint_error_rate:
                    wrong = _misread(value, profile_id, page.page_id, row.row, name)
                    fields[name] = _field(
                        wrong,
                        "known" if profile.overconfidence else "uncertain",
                        0.6 + profile.overconfidence,
                        region,
                        alternatives=[value] if value and not profile.overconfidence else None,
                    )
                else:
                    fields[name] = _field(
                        value, "known", 0.72 + 0.1 * noise, region, alternatives=[value]
                    )

            elif legibility == ILLEGIBLE:
                if profile.fabricates_unreadable:
                    fields[name] = _field(
                        _fabricated_value(profile_id, page.page_id, row.row, name),
                        "known",
                        0.88,
                        region,
                    )
                else:
                    fields[name] = _field(None, "unreadable", 0.0, region)

            elif legibility == BLANK:
                if profile.fabricates_unreadable and noise < 0.5:
                    fields[name] = _field(
                        _fabricated_value(profile_id, page.page_id, row.row, name), "known", 0.8, region
                    )
                else:
                    fields[name] = _field(None, "absent", 0.9, region)

            else:  # pragma: no cover - guards against a new legibility value
                raise ValueError(f"unknown legibility {legibility!r} for {name}")

        entries.append(
            {
                "index_entry_id": f"{page.page_id}_r{row.row}",
                "page_id": page.page_id,
                "row": row.row,
                "notes": "",
                "fields": fields,
            }
        )
    return entries


def read_corpus(profile_id: str, pages) -> list[dict]:
    entries: list[dict] = []
    for page in pages:
        entries.extend(read_page(profile_id, page))
    return entries
