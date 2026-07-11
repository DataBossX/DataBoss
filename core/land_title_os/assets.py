"""Master asset inventory (Move #3) — SQLite registry of every known asset.

Every asset gets a stable ID, location, SHA-256, project linkage, duplicate
group, and security classification. Re-registering the same path+hash is
idempotent, so agents stop rediscovering and duplicating work.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from .util import sha256_file, stable_id, utcnow_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS assets (
    asset_id            TEXT PRIMARY KEY,
    location            TEXT NOT NULL,
    store               TEXT NOT NULL DEFAULT 'local',   -- local | gdrive | dropbox | github | web
    sha256              TEXT,
    size_bytes          INTEGER,
    file_type           TEXT,
    project_id          TEXT,
    section             TEXT,
    county              TEXT,
    state               TEXT,
    version             TEXT,
    status              TEXT NOT NULL DEFAULT 'SOURCE',  -- promotion stage or classification
    source_authority    INTEGER,                          -- evidence.AUTHORITY rank (1 = highest)
    security_class      TEXT NOT NULL DEFAULT 'internal', -- public | internal | client-confidential
    duplicate_group     TEXT,
    relationships       TEXT,                             -- JSON list of related asset_ids
    last_verified       TEXT,
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assets_sha256 ON assets (sha256);
CREATE INDEX IF NOT EXISTS idx_assets_project ON assets (project_id);
"""


@dataclass
class Asset:
    asset_id: str
    location: str
    store: str = "local"
    sha256: str | None = None
    size_bytes: int | None = None
    file_type: str | None = None
    project_id: str | None = None
    section: str | None = None
    county: str | None = None
    state: str | None = None
    version: str | None = None
    status: str = "SOURCE"
    source_authority: int | None = None
    security_class: str = "internal"
    duplicate_group: str | None = None
    relationships: str | None = None
    last_verified: str | None = None
    created_at: str = field(default_factory=utcnow_iso)


class AssetInventory:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # -- registration ------------------------------------------------------

    def register_file(self, path: str | Path, **meta) -> Asset:
        """Hash and register a local file. Idempotent on (path, sha256)."""
        p = Path(path)
        digest = sha256_file(p)
        asset = Asset(
            asset_id=stable_id("AST", str(p.resolve()), digest),
            location=str(p.resolve()),
            sha256=digest,
            size_bytes=p.stat().st_size,
            file_type=p.suffix.lstrip(".").lower() or "none",
            last_verified=utcnow_iso(),
            **meta,
        )
        self._upsert(asset)
        return asset

    def register_remote(self, location: str, store: str, **meta) -> Asset:
        """Register a non-local asset (Drive file ID/URL, Dropbox path, repo)."""
        asset = Asset(
            asset_id=stable_id("AST", store, location),
            location=location,
            store=store,
            **meta,
        )
        self._upsert(asset)
        return asset

    def scan_directory(self, root: str | Path, project_id: str | None = None,
                       exclude_dirs: tuple = (".git", "__pycache__", "node_modules",
                                              ".venv", "venv", "output")) -> list[Asset]:
        """Inventory every file under root (read-only; source folders untouched)."""
        registered = []
        for p in sorted(Path(root).rglob("*")):
            if p.is_dir() or any(part in exclude_dirs for part in p.parts):
                continue
            registered.append(self.register_file(p, project_id=project_id))
        self.assign_duplicate_groups()
        return registered

    def _upsert(self, asset: Asset) -> None:
        cols = list(Asset.__dataclass_fields__)
        placeholders = ",".join("?" for _ in cols)
        self._conn.execute(
            f"INSERT OR REPLACE INTO assets ({','.join(cols)}) VALUES ({placeholders})",
            [getattr(asset, c) for c in cols],
        )
        self._conn.commit()

    # -- duplicates (Move #29) ---------------------------------------------

    def assign_duplicate_groups(self) -> int:
        """Group byte-identical assets by SHA-256. Returns group count."""
        rows = self._conn.execute(
            "SELECT sha256 FROM assets WHERE sha256 IS NOT NULL "
            "GROUP BY sha256 HAVING COUNT(*) > 1"
        ).fetchall()
        for row in rows:
            group = stable_id("DUP", row["sha256"])
            self._conn.execute(
                "UPDATE assets SET duplicate_group = ? WHERE sha256 = ?",
                (group, row["sha256"]),
            )
        self._conn.commit()
        return len(rows)

    # -- queries -------------------------------------------------------------

    def get(self, asset_id: str) -> sqlite3.Row | None:
        return self._conn.execute(
            "SELECT * FROM assets WHERE asset_id = ?", (asset_id,)
        ).fetchone()

    def by_project(self, project_id: str) -> list[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM assets WHERE project_id = ? ORDER BY location", (project_id,)
        ).fetchall()

    def duplicate_groups(self) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {}
        for row in self._conn.execute(
            "SELECT duplicate_group, location FROM assets "
            "WHERE duplicate_group IS NOT NULL ORDER BY duplicate_group, location"
        ):
            groups.setdefault(row["duplicate_group"], []).append(row["location"])
        return groups

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
