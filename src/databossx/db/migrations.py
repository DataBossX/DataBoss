"""Numbered SQL migration runner for the DataBossX SQLite database.

Migration files live in a directory and are named ``NNN_name.sql`` (for
example ``001_initial.sql``). Applied migrations are tracked in a
``schema_migrations`` table. Each migration is applied inside a single
transaction; if it fails, the transaction is rolled back and the error is
re-raised so the caller can react.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_MIGRATION_NAME_RE = re.compile(r"^(\d+)_(.+)\.sql$")


@dataclass(frozen=True)
class _MigrationFile:
    number: int
    name: str
    path: Path


class MigrationRunner:
    """Applies numbered ``.sql`` migration files to a SQLite database."""

    def __init__(self, db_path: str | Path, migrations_dir: Path) -> None:
        self.db_path = str(db_path)
        self.migrations_dir = Path(migrations_dir)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_bookkeeping_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                number INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        conn.commit()

    def _discover_migrations(self) -> list[_MigrationFile]:
        migrations: list[_MigrationFile] = []
        if not self.migrations_dir.is_dir():
            return migrations
        for path in sorted(self.migrations_dir.glob("*.sql")):
            match = _MIGRATION_NAME_RE.match(path.name)
            if not match:
                continue
            number = int(match.group(1))
            name = match.group(2)
            migrations.append(_MigrationFile(number=number, name=name, path=path))
        migrations.sort(key=lambda m: m.number)
        return migrations

    def current_version(self) -> int:
        """Return the highest applied migration number (0 = none applied)."""
        conn = self._connect()
        try:
            self._ensure_bookkeeping_table(conn)
            row = conn.execute(
                "SELECT COALESCE(MAX(number), 0) FROM schema_migrations"
            ).fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()

    def status(self) -> list[dict]:
        """Return ``{number, name, applied_at}`` for every discovered migration."""
        conn = self._connect()
        try:
            self._ensure_bookkeeping_table(conn)
            applied = {
                row[0]: row[2]
                for row in conn.execute(
                    "SELECT number, name, applied_at FROM schema_migrations"
                ).fetchall()
            }
        finally:
            conn.close()

        results: list[dict] = []
        for migration in self._discover_migrations():
            results.append(
                {
                    "number": migration.number,
                    "name": migration.name,
                    "applied_at": applied.get(migration.number),
                }
            )
        return results

    def run(self) -> int:
        """Apply all unapplied migrations in order; return count applied."""
        conn = self._connect()
        applied_count = 0
        try:
            self._ensure_bookkeeping_table(conn)
            applied_numbers = {
                row[0]
                for row in conn.execute("SELECT number FROM schema_migrations").fetchall()
            }
            for migration in self._discover_migrations():
                if migration.number in applied_numbers:
                    continue
                sql_text = migration.path.read_text(encoding="utf-8")
                # executescript issues an implicit COMMIT of any pending
                # transaction before running, then executes the script
                # verbatim (it does not wrap it in a transaction itself).
                # We supply our own BEGIN/COMMIT inside the script text so
                # the whole migration is atomic; on failure we roll back.
                wrapped_script = f"BEGIN;\n{sql_text}\nCOMMIT;"
                try:
                    conn.executescript(wrapped_script)
                    conn.execute(
                        "INSERT INTO schema_migrations (number, name, applied_at) "
                        "VALUES (?, ?, ?)",
                        (
                            migration.number,
                            migration.name,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                applied_count += 1
        finally:
            conn.close()
        return applied_count


def main() -> None:
    """CLI entry point: ``python -m databossx.db.migrations <db_path> <migrations_dir>``."""
    parser = argparse.ArgumentParser(description="Run DataBossX SQL migrations.")
    parser.add_argument("db_path", help="Path to the SQLite database file.")
    parser.add_argument(
        "migrations_dir",
        nargs="?",
        default="migrations",
        help="Directory containing NNN_name.sql migration files (default: ./migrations).",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print migration status instead of applying migrations.",
    )
    args = parser.parse_args()

    runner = MigrationRunner(args.db_path, Path(args.migrations_dir))
    if args.status:
        for entry in runner.status():
            print(f"{entry['number']:04d} {entry['name']:40s} {entry['applied_at']}")
        return

    applied = runner.run()
    print(f"Applied {applied} migration(s). Current version: {runner.current_version()}")


if __name__ == "__main__":
    main()
