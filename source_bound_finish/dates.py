"""Date-role isolation. One role never fills another blank."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .constants import DATE_ROLES, FORBIDDEN_COMMENT_VALUES


class DateRoleError(ValueError):
    pass


@dataclass(frozen=True)
class DateRoleFinding:
    role: str
    code: str
    message: str
    row: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def check_date_roles(record: dict, *, row: int | None = None) -> list[DateRoleFinding]:
    """Check that supplied date roles are independent and non-placeholder.

    Missing roles stay blank. A preparation date is never treated as
    search-through or instrument currentness.
    """
    findings: list[DateRoleFinding] = []
    present: dict[str, str] = {}
    for role in DATE_ROLES:
        raw = record.get(role)
        text = _normalize(raw)
        if not text:
            continue
        if text.lower() in FORBIDDEN_COMMENT_VALUES:
            findings.append(
                DateRoleFinding(role, "PLACEHOLDER", "placeholder is not a date", row)
            )
            continue
        present[role] = text

    if record.get("copied_from"):
        source_role = str(record["copied_from"])
        target_role = str(record.get("copied_into") or "")
        if source_role and target_role and source_role != target_role:
            findings.append(
                DateRoleFinding(
                    target_role,
                    "ROLE_BLEED",
                    f"{source_role} must not fill {target_role}",
                    row,
                )
            )
    preparation = present.get("preparation")
    if preparation and present.get("search_through") == preparation:
        findings.append(
            DateRoleFinding(
                "search_through",
                "PREP_IS_NOT_CURRENTNESS",
                "preparation date is not a search-through date",
                row,
            )
        )
    return findings


def check_date_table(rows: list[dict]) -> list[DateRoleFinding]:
    findings: list[DateRoleFinding] = []
    for index, row in enumerate(rows, start=1):
        findings.extend(check_date_roles(row, row=index))
    return findings
