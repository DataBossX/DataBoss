"""
Database layer with support for SQLite and PostgreSQL/Supabase.
Handles migrations, caching, and evidence tracking.
"""

import logging
import os
from typing import Optional, Dict, List
from datetime import datetime
from pathlib import Path
import json
import uuid

logger = logging.getLogger(__name__)


class Database:
    """
    Database abstraction layer.

    Supports both SQLite (local dev) and PostgreSQL (production).
    Switch via environment variable or config.
    """

    def __init__(self, db_type: Optional[str] = None, connection_string: Optional[str] = None):
        """
        Initialize database.

        Args:
            db_type: 'sqlite' or 'postgres'. If None, checks env var DB_TYPE
            connection_string: Database connection string. If None, uses defaults
        """
        self.db_type = db_type or os.getenv('DB_TYPE', 'sqlite')
        self.connection_string = connection_string or self._get_default_connection()

        # Initialize connection
        if self.db_type == 'sqlite':
            import sqlite3
            self.conn = sqlite3.connect(self.connection_string)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Connected to SQLite: {self.connection_string}")
        elif self.db_type == 'postgres':
            import psycopg2
            from psycopg2.extras import RealDictCursor
            self.conn = psycopg2.connect(self.connection_string)
            self.cursor_factory = RealDictCursor
            logger.info("Connected to PostgreSQL")
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

        # Run migrations
        self._run_migrations()

    def _get_default_connection(self) -> str:
        """Get default connection string based on db_type."""
        if self.db_type == 'sqlite':
            db_path = os.getenv('SQLITE_PATH', 'db/local_cache.sqlite')
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            return db_path
        elif self.db_type == 'postgres':
            # Read from environment or use Supabase connection
            return os.getenv('DATABASE_URL', 'postgresql://localhost/notice_list')
        else:
            return ''

    def _run_migrations(self):
        """Run database migrations."""
        try:
            # Check if this is first run
            cursor = self.conn.cursor()

            if self.db_type == 'sqlite':
                cursor.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='cases'
                """)
            else:
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema='public' AND table_name='cases'
                """)

            if not cursor.fetchone():
                logger.info("Running initial schema migration...")
                self._apply_schema()

            cursor.close()

        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)

    def _apply_schema(self):
        """Apply database schema."""
        schema_path = Path(__file__).parent / "enhanced_schema.sql"

        if not schema_path.exists():
            logger.warning(f"Schema file not found: {schema_path}")
            return

        with open(schema_path) as f:
            schema_sql = f.read()

        # SQLite compatibility adjustments
        if self.db_type == 'sqlite':
            schema_sql = schema_sql.replace('UUID', 'TEXT')
            schema_sql = schema_sql.replace('JSONB', 'TEXT')
            schema_sql = schema_sql.replace('gen_random_uuid()', "hex(randomblob(16))")
            schema_sql = schema_sql.replace('GEOMETRY(Polygon, 4326)', 'TEXT')
            schema_sql = schema_sql.replace('DECIMAL', 'REAL')

            # Remove unsupported PostgreSQL features
            schema_sql = schema_sql.split('-- ROW LEVEL SECURITY')[0]

        # Execute schema
        cursor = self.conn.cursor()

        for statement in schema_sql.split(';'):
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                try:
                    cursor.execute(statement)
                except Exception as e:
                    # Some statements might fail (e.g., IF NOT EXISTS on existing objects)
                    logger.debug(f"Schema statement warning: {e}")

        self.conn.commit()
        cursor.close()

        logger.info("Schema applied successfully")

    def save_case(self, case) -> str:
        """
        Save a Case object to database.

        Args:
            case: Case object

        Returns:
            Case ID (UUID)
        """
        case_id = case.case_id or str(uuid.uuid4())

        cursor = self.conn.cursor()

        if self.db_type == 'sqlite':
            cursor.execute("""
                INSERT INTO cases (
                    id, unit_name, county, state, plss_meridian,
                    status, source_files, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                case_id,
                case.unit_name,
                case.county,
                case.state,
                case.plss_meridian,
                case.status,
                json.dumps(case.source_files),
                case.created_at.isoformat(),
                case.updated_at.isoformat()
            ))
        else:
            cursor.execute("""
                INSERT INTO cases (
                    id, unit_name, county, state, plss_meridian,
                    status, source_files, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                case_id,
                case.unit_name,
                case.county,
                case.state,
                case.plss_meridian,
                case.status,
                json.dumps(case.source_files),
                case.created_at,
                case.updated_at
            ))

        self.conn.commit()
        cursor.close()

        logger.info(f"Saved case {case_id}")

        return case_id

    def save_evidence(
        self,
        evidence_type: str,
        source: str,
        interest_id: Optional[str] = None,
        address_id: Optional[str] = None,
        lease_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Save evidence record.

        Args:
            evidence_type: Type of evidence
            source: Source system
            interest_id: Related interest ID
            address_id: Related address ID
            lease_id: Related lease ID
            **kwargs: Additional evidence fields

        Returns:
            Evidence ID
        """
        evidence_id = str(uuid.uuid4())

        cursor = self.conn.cursor()

        placeholder = '?' if self.db_type == 'sqlite' else '%s'

        cursor.execute(f"""
            INSERT INTO evidence (
                id, interest_id, address_id, lease_id,
                evidence_type, source, document_type, recording_number,
                recording_date, document_url, confidence_score, metadata, created_at
            ) VALUES (
                {placeholder}, {placeholder}, {placeholder}, {placeholder},
                {placeholder}, {placeholder}, {placeholder}, {placeholder},
                {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}
            )
        """, (
            evidence_id,
            interest_id,
            address_id,
            lease_id,
            evidence_type,
            source,
            kwargs.get('document_type'),
            kwargs.get('recording_number'),
            kwargs.get('recording_date'),
            kwargs.get('document_url'),
            kwargs.get('confidence_score', 0.0),
            json.dumps(kwargs.get('metadata', {})),
            datetime.now() if self.db_type == 'postgres' else datetime.now().isoformat()
        ))

        self.conn.commit()
        cursor.close()

        return evidence_id

    def log_processing(
        self,
        case_id: str,
        action: str,
        status: str,
        message: str,
        details: Optional[Dict] = None
    ):
        """
        Log processing event.

        Args:
            case_id: Case ID
            action: Action type
            status: Status (success/failure/warning)
            message: Log message
            details: Optional details dict
        """
        cursor = self.conn.cursor()

        log_id = str(uuid.uuid4())
        placeholder = '?' if self.db_type == 'sqlite' else '%s'

        cursor.execute(f"""
            INSERT INTO processing_log (
                id, case_id, action, status, message, details, timestamp
            ) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
        """, (
            log_id,
            case_id,
            action,
            status,
            message,
            json.dumps(details or {}),
            datetime.now() if self.db_type == 'postgres' else datetime.now().isoformat()
        ))

        self.conn.commit()
        cursor.close()

    def update_connector_stats(
        self,
        connector_name: str,
        success: bool,
        response_time_ms: Optional[float] = None
    ):
        """
        Update connector scorecard.

        Args:
            connector_name: Connector name
            success: Whether operation succeeded
            response_time_ms: Response time in milliseconds
        """
        cursor = self.conn.cursor()

        placeholder = '?' if self.db_type == 'sqlite' else '%s'

        # Check if record exists
        cursor.execute(f"""
            SELECT id FROM connector_scorecard WHERE connector_name = {placeholder}
        """, (connector_name,))

        exists = cursor.fetchone()

        if exists:
            # Update existing
            if success:
                cursor.execute(f"""
                    UPDATE connector_scorecard
                    SET success_count = success_count + 1,
                        total_requests = total_requests + 1,
                        last_success_at = {placeholder},
                        updated_at = {placeholder}
                    WHERE connector_name = {placeholder}
                """, (
                    datetime.now() if self.db_type == 'postgres' else datetime.now().isoformat(),
                    datetime.now() if self.db_type == 'postgres' else datetime.now().isoformat(),
                    connector_name
                ))
            else:
                cursor.execute(f"""
                    UPDATE connector_scorecard
                    SET failure_count = failure_count + 1,
                        total_requests = total_requests + 1,
                        last_failure_at = {placeholder},
                        updated_at = {placeholder}
                    WHERE connector_name = {placeholder}
                """, (
                    datetime.now() if self.db_type == 'postgres' else datetime.now().isoformat(),
                    datetime.now() if self.db_type == 'postgres' else datetime.now().isoformat(),
                    connector_name
                ))
        else:
            # Insert new
            cursor.execute(f"""
                INSERT INTO connector_scorecard (
                    id, connector_name, success_count, failure_count, total_requests,
                    last_success_at, last_failure_at, created_at, updated_at
                ) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """, (
                str(uuid.uuid4()),
                connector_name,
                1 if success else 0,
                0 if success else 1,
                1,
                datetime.now() if success and self.db_type == 'postgres' else (datetime.now().isoformat() if success else None),
                None if success else (datetime.now() if self.db_type == 'postgres' else datetime.now().isoformat()),
                datetime.now() if self.db_type == 'postgres' else datetime.now().isoformat(),
                datetime.now() if self.db_type == 'postgres' else datetime.now().isoformat()
            ))

        self.conn.commit()
        cursor.close()

    def get_audit_queue(self, limit: int = 100) -> List[Dict]:
        """
        Get pending audit items.

        Args:
            limit: Maximum items to return

        Returns:
            List of audit items
        """
        cursor = self.conn.cursor()

        placeholder = '?' if self.db_type == 'sqlite' else '%s'

        cursor.execute(f"""
            SELECT * FROM audit_queue
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
            LIMIT {placeholder}
        """, (limit,))

        items = []
        for row in cursor.fetchall():
            if self.db_type == 'sqlite':
                items.append(dict(row))
            else:
                items.append(row)

        cursor.close()

        return items

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
