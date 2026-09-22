"""Shared enums and fail-closed rules. No client facts live here."""

from __future__ import annotations

DISPOSITIONS = (
    "MATERIAL_START",
    "CONTINUATION",
    "OPERATIVE_EXHIBIT",
    "OPERATIVE_SCHEDULE",
    "SUPPORT_ONLY",
    "ROUTING_TRANSMITTAL",
    "SRP_CURRENTNESS_SUPPORT",
    "DUPLICATE_COPY",
    "NON_TARGET",
    "BLANK",
    "UNREADABLE",
    "MISSING_SOURCE",
    "UNRESOLVED",
)

CLIENT_ROW_DISPOSITIONS = frozenset({"MATERIAL_START"})

DATE_ROLES = (
    "execution",
    "recording",
    "received",
    "effective",
    "approval",
    "filed",
    "search_through",
    "preparation",
)

FORBIDDEN_COMMENT_VALUES = frozenset(
    {
        "hold",
        "unknown",
        "n/a",
        "na",
        "none",
        "tbd",
        "todo",
        "confidence",
        "provenance",
        "ocr",
        "ai note",
        "ai notes",
        "review",
        "needs review",
    }
)

ALLOWED_COMMENT_EXACT = frozenset({"", "missing image"})

GENERIC_PARTY_TOKENS = frozenset(
    {
        "et al",
        "et. al",
        "et.al",
        "affiant",
        "assignees",
        "assignors",
        "heirs",
        "unknown",
    }
)

PROCESS_COMMENTARY_MARKERS = (
    "see qa",
    "per ocr",
    "model inferred",
    "source path",
    "confidence",
    "hold:",
    "unresolved:",
    "needs examiner",
    "ai:",
)

COUNTY_COLUMNS = (
    "Document Type",
    "Grantor",
    "Grantee",
    "Book",
    "Page",
    "Doc No",
    "Date of Doc",
    "Rec Date",
    "Legal Description",
)

FEDERAL_COLUMNS = (
    "Document Type",
    "Grantor",
    "Grantee",
    "Page",
    "Date of Doc",
    "Rec Date",
    "Legal Description",
    "Part",
)

REDUCED_FEDERAL_COLUMNS = (
    "Document Type",
    "Grantor",
    "Grantee",
    "Page",
    "Date of Doc",
    "Rec Date",
    "Legal Description",
)

FORBIDDEN_PROCESS_COLUMNS = frozenset(
    {
        "file no",
        "filename",
        "source",
        "confidence",
        "ocr",
        "notes",
        "qa",
        "provenance",
        "status",
        "hold",
    }
)
