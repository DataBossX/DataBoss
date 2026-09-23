"""Non-destructive sync planner.

Compares two registered roots (for example a local working folder and a Drive
export mirror). The planner never deletes, never overwrites originals, and
never writes to Drive. Apply copies missing bytes into the project vault only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..config import DataBossConfig
from ..hashing import copy_file_to_vault, sha256_file
from ..policy import PolicyEngine
from .base import ConnectorItem
from .drive import DriveWriteRefused


@dataclass(frozen=True)
class SyncAction:
    action: str  # copy_to_vault | missing_on_left | missing_on_right | hash_mismatch | identical
    relative_path: str
    left_checksum: str = ""
    right_checksum: str = ""
    source_locator: str = ""


@dataclass
class SyncPlan:
    actions: list[SyncAction] = field(default_factory=list)
    write_to_provider: bool = False

    @property
    def vault_copies(self) -> list[SyncAction]:
        return [a for a in self.actions if a.action == "copy_to_vault"]

    def to_json(self) -> str:
        return json.dumps(
            {
                "write_to_provider": self.write_to_provider,
                "actions": [a.__dict__ for a in self.actions],
            },
            indent=2,
            sort_keys=True,
        )


def index_items(items: list[ConnectorItem]) -> dict[str, ConnectorItem]:
    return {item.provider_id.replace("\\", "/"): item for item in items}


def plan_sync(
    left: list[ConnectorItem],
    right: list[ConnectorItem],
    *,
    copy_missing_to_vault: bool = True,
) -> SyncPlan:
    left_map = index_items(left)
    right_map = index_items(right)
    keys = sorted(set(left_map) | set(right_map))
    actions: list[SyncAction] = []
    for key in keys:
        lft = left_map.get(key)
        rgt = right_map.get(key)
        if lft and rgt:
            if lft.checksum and rgt.checksum and lft.checksum == rgt.checksum:
                actions.append(
                    SyncAction("identical", key, lft.checksum, rgt.checksum, lft.locator)
                )
            elif lft.checksum and rgt.checksum and lft.checksum != rgt.checksum:
                actions.append(
                    SyncAction("hash_mismatch", key, lft.checksum, rgt.checksum, lft.locator)
                )
            else:
                actions.append(SyncAction("identical", key, lft.checksum, rgt.checksum, lft.locator))
        elif lft and copy_missing_to_vault:
            actions.append(SyncAction("copy_to_vault", key, lft.checksum, "", lft.locator))
        elif lft:
            actions.append(SyncAction("missing_on_right", key, lft.checksum, "", lft.locator))
        else:
            actions.append(SyncAction("copy_to_vault", key, "", rgt.checksum, rgt.locator))
    return SyncPlan(actions=actions, write_to_provider=False)


def apply_vault_ingest(
    config: DataBossConfig,
    project_id: str,
    plan: SyncPlan,
    *,
    policy: PolicyEngine | None = None,
) -> list[str]:
    engine = policy or PolicyEngine()
    if plan.write_to_provider:
        raise DriveWriteRefused("sync apply refuses provider writes")
    decision = engine.allow_vault_ingest()
    if not decision.allowed:
        raise DriveWriteRefused(decision.reason)
    ingested: list[str] = []
    vault_root = config.project_vault_root(project_id)
    for action in plan.vault_copies:
        source = Path(action.source_locator)
        if not source.is_file():
            continue
        stored = copy_file_to_vault(source, vault_root)
        if stored.sha256 != sha256_file(source):
            raise DriveWriteRefused("vault copy hash mismatch; ingest refused")
        ingested.append(stored.sha256)
    return ingested
