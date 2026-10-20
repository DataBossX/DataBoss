from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

COUNTY_SCHEMA_DEFAULT = [
    "Index No", "Tract", "Instrument Type", "Grantor", "Grantee",
    "Recording Date", "Recorder ID", "Source PDF", "PDF Page",
]
FEDERAL_SCHEMA_DEFAULT = [
    "Serial No", "Event Date", "Event Type", "Lessee/Assignor", "Assignee",
    "Tract", "Acres", "Status", "Source PDF", "PDF Page",
]

DEFAULTS: dict[str, Any] = {
    "project_label": "EXAMPLE",
    "source_roots": [],
    "protected_paths": [],
    "output_root": "",
    "claimed_placements": None,
    "expected_sources": [],
    "baseline_manifest": None,
    "max_zip_depth": 3,
    "max_parse_bytes": 256 * 1024 * 1024,
    "section_rules": [{"regex": r"(?i)(?<![A-Za-z0-9])(?P<section>[RT]\d{1,3})(?![A-Za-z0-9])"}],
    "branch_groups": {},
    "donor_section": None,
    "owner_overrides": {},
    "county_schema": COUNTY_SCHEMA_DEFAULT,
    "federal_schema": FEDERAL_SCHEMA_DEFAULT,
    "table_kind_rules": [
        {"regex": r"(?i)federal|blm|wyw", "kind": "federal"},
        {"regex": r"(?i)county|recorder", "kind": "county"},
    ],
    "forbidden_headers": ["BLM File No", "Comments"],
    "forbidden_value_patterns": [r"(?i)\bBLM\s+File\s+No\b"],
    "narrative_patterns": [
        r"(?i)\bno\s+(instruments?|records?|documents?|entries)\b",
        r"(?i)\bnone\s+of\s+record\b",
        r"(?i)^n/?a$",
        r"(?i)\bnot\s+applicable\b",
        r"(?i)\bnarrative\b",
        r"(?i)\bsee\s+(note|notes|narrative|below|above)\b",
        r"(?i)\breserved\b",
        r"(?i)\btbd\b",
        r"^[-—–_.\s]+$",
        r"(?i)^notes?:",
    ],
    "recorder_id_field": "Recorder ID",
    "county_default": "",
    "compare_fields": ["Instrument Type", "Grantor", "Grantee", "Recording Date"],
    "federal_serial_field": "Serial No",
    "federal_date_field": "Event Date",
    "federal_type_field": "Event Type",
    "source_pdf_field": "Source PDF",
    "pdf_page_field": "PDF Page",
    "tract_field": "Tract",
    "serial_regex": r"(?i)WYW\s*0*(\d+)",
    "serial_prefix": "WYW",
    "cloud_markers": ["onedrive", "dropbox", "google drive", "googledrive", "icloud", "box sync", "box/", "sharepoint", "my drive"],
}


class ConfigError(ValueError):
    pass


def load_config(path: str | Path | None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = copy.deepcopy(DEFAULTS)
    if path:
        with open(path, "r", encoding="utf-8") as fh:
            user = json.load(fh)
        unknown = set(user) - set(DEFAULTS) - {"_comment"}
        if unknown:
            raise ConfigError(f"unknown config keys: {sorted(unknown)}")
        cfg.update(user)
    if overrides:
        cfg.update(overrides)
    validate(cfg)
    return cfg


def validate(cfg: dict[str, Any]) -> None:
    if len(cfg["county_schema"]) != 9:
        raise ConfigError("county_schema must have exactly 9 columns")
    if len(cfg["federal_schema"]) != 10:
        raise ConfigError("federal_schema must have exactly 10 columns")
    if not cfg["output_root"]:
        raise ConfigError("output_root is required")
    if not cfg["source_roots"]:
        raise ConfigError("source_roots is required")
    for rule in cfg["section_rules"]:
        if "regex" not in rule:
            raise ConfigError("each section_rule needs 'regex'")
    seen: dict[str, str] = {}
    for g, members in cfg["branch_groups"].items():
        for m in members:
            if m in seen:
                raise ConfigError(f"section {m} appears in branch groups {seen[m]} and {g}")
            seen[m] = g
