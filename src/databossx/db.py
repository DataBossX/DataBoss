from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import KernelConfig


class MigrationError(RuntimeError):
    pass


class Database:
    def __init__(self, config: KernelConfig) -> None:
        self.config = config

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.config.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def initialize(self) -> None:
        self.config.initialize_directories()
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            for migration in sorted(self.config.migrations_root.glob("*.sql")):
                self._apply_migration(connection, migration)
            connection.execute(
                """
                UPDATE ingest_runs
                   SET status = 'INTERRUPTED',
                       completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP),
                       error = COALESCE(error, 'Process stopped before completion')
                 WHERE status = 'RUNNING'
                """
            )

    def _apply_migration(
        self, connection: sqlite3.Connection, migration: Path
    ) -> None:
        content = migration.read_bytes()
        checksum = hashlib.sha256(content).hexdigest()
        applied = connection.execute(
            "SELECT sha256 FROM schema_migrations WHERE filename = ?",
            (migration.name,),
        ).fetchone()
        if applied:
            if applied["sha256"] != checksum:
                raise MigrationError(
                    f"Applied migration changed on disk: {migration.name}"
                )
            return
        try:
            connection.executescript(content.decode("utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations(filename, sha256) VALUES (?, ?)",
                (migration.name, checksum),
            )
        except sqlite3.DatabaseError as exc:
            raise MigrationError(f"Migration {migration.name} failed: {exc}") from exc

    @contextmanager
    def transaction(self, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
