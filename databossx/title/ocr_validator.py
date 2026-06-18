"""OCR result validator for DataBossX.

Enforces the strict schema and the operating rules:
  * exact key set (no extra/missing keys)
  * correct types (scalars nullable, lists are lists)
  * confidence is a float in [0, 1]
  * any non-null fact requires at least one `visible_evidence` entry

Returns (ok, errors). Treats OCR as *suggested evidence*, never truth.
"""
from __future__ import annotations

from . import document_schema as schema


def validate(result: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(result, dict):
        return False, ["result is not a JSON object"]

    expected = set(schema.OCR_SCHEMA.keys())
    actual = set(result.keys())
    missing = expected - actual
    extra = actual - expected
    if missing:
        errors.append(f"missing keys: {sorted(missing)}")
    if extra:
        errors.append(f"unexpected keys: {sorted(extra)}")

    for field in schema.SCALAR_FIELDS & actual:
        val = result[field]
        if val is not None and not isinstance(val, (str, int, float)):
            errors.append(f"scalar field '{field}' must be null or a primitive")

    for field in schema.LIST_FIELDS & actual:
        if not isinstance(result.get(field), list):
            errors.append(f"list field '{field}' must be a list")

    conf = result.get("confidence")
    if not isinstance(conf, (int, float)) or isinstance(conf, bool):
        errors.append("confidence must be a number")
    elif not (0.0 <= float(conf) <= 1.0):
        errors.append("confidence must be within [0, 1]")

    # Evidence rule: if any title fact is asserted, evidence must back it.
    asserted = any(
        result.get(f) not in (None, [], "")
        for f in schema.SCALAR_FIELDS | {"grantors", "grantees", "legal_descriptions"}
        if f in result
    )
    evidence = result.get("visible_evidence")
    if asserted and isinstance(evidence, list) and len(evidence) == 0:
        errors.append("non-null facts asserted but visible_evidence is empty")

    return (len(errors) == 0), errors
