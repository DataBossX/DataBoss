"""
Local SQLite cache for tract, owner, and address data.
"""

import logging
import sqlite3
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class LocalCache:
    """SQLite cache for notice list data."""

    def __init__(self, db_path: str = "db/local_cache.sqlite"):
        """
        Initialize cache.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """Create database and tables if they don't exist."""
        # Create directory if needed
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Load schema
        schema_path = Path(__file__).parent / "schema.sql"

        if not schema_path.exists():
            logger.warning(f"Schema file not found: {schema_path}")
            return

        with sqlite3.connect(self.db_path) as conn:
            with open(schema_path) as f:
                conn.executescript(f.read())

        logger.info(f"Database initialized: {self.db_path}")

    def cache_tract(
        self,
        tract_id: str,
        legal_description: str,
        **kwargs
    ) -> None:
        """
        Cache tract information.

        Args:
            tract_id: Tract identifier
            legal_description: Legal description
            **kwargs: Additional tract fields
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO tracts
                (tract_id, legal_description, township, range, section,
                 gross_acres, net_acres, source, source_file, confidence_score, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tract_id,
                legal_description,
                kwargs.get("township"),
                kwargs.get("range"),
                kwargs.get("section"),
                kwargs.get("gross_acres"),
                kwargs.get("net_acres"),
                kwargs.get("source"),
                kwargs.get("source_file"),
                kwargs.get("confidence_score", 0.0),
                datetime.now()
            ))

            conn.commit()

    def cache_owner(
        self,
        owner_name: str,
        tract_id: str,
        ownership_type: str,
        **kwargs
    ) -> None:
        """
        Cache owner information.

        Args:
            owner_name: Owner name
            tract_id: Associated tract ID
            ownership_type: Type of ownership
            **kwargs: Additional fields
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO owners
                (owner_name, tract_id, ownership_type, interest_decimal,
                 interest_fraction, source, confidence_score, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                owner_name,
                tract_id,
                ownership_type,
                kwargs.get("interest_decimal"),
                kwargs.get("interest_fraction"),
                kwargs.get("source"),
                kwargs.get("confidence_score", 0.0),
                datetime.now()
            ))

            conn.commit()

    def cache_address(
        self,
        owner_name: str,
        street: str,
        city: str,
        state: str,
        zip_code: str,
        source: str,
        **kwargs
    ) -> None:
        """
        Cache address information.

        Args:
            owner_name: Owner name
            street: Street address
            city: City
            state: State
            zip_code: ZIP code
            source: Address source
            **kwargs: Additional fields
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO addresses
                (owner_name, street, city, state, zip_code, country,
                 source, source_date, confidence_score, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                owner_name,
                street,
                city,
                state,
                zip_code,
                kwargs.get("country", "USA"),
                source,
                kwargs.get("source_date"),
                kwargs.get("confidence_score", 0.0),
                datetime.now()
            ))

            conn.commit()

    def get_cached_address(self, owner_name: str) -> Optional[Dict]:
        """
        Get cached address for owner.

        Args:
            owner_name: Owner name

        Returns:
            Address dictionary or None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM addresses
                WHERE owner_name = ?
                ORDER BY confidence_score DESC, source_date DESC
                LIMIT 1
            """, (owner_name,))

            row = cursor.fetchone()

            if row:
                return dict(row)

        return None

    def log_processing(
        self,
        unit_name: str,
        action: str,
        status: str,
        message: str,
        details: Optional[str] = None
    ) -> None:
        """
        Log processing action.

        Args:
            unit_name: Unit name
            action: Action type
            status: Status (success/failure/warning)
            message: Log message
            details: Optional JSON details
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO processing_log
                (unit_name, action, status, message, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                unit_name,
                action,
                status,
                message,
                details,
                datetime.now()
            ))

            conn.commit()

    def cleanup_old_cache(self, days: int = 30) -> int:
        """
        Clean up cache entries older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of rows deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM processing_log
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (days,))

            deleted = cursor.rowcount
            conn.commit()

        logger.info(f"Deleted {deleted} old cache entries")
        return deleted
