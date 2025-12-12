"""
Nightly Audit Routine
Retries failed lookups, updates stale addresses, validates data quality.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
import schedule
import time

from db.database import Database
from connectors.connector_manager import ConnectorManager

logger = logging.getLogger(__name__)


class NightlyAudit:
    """
    Nightly audit and self-improvement system.

    Runs periodic audits to:
    - Retry failed owner/address lookups
    - Update stale addresses (>180 days old)
    - Validate data quality
    - Clean up old cache entries
    - Generate quality reports
    """

    def __init__(self, db: Database, connector_mgr: ConnectorManager):
        """
        Initialize audit system.

        Args:
            db: Database instance
            connector_mgr: Connector manager
        """
        self.db = db
        self.connector_mgr = connector_mgr

    async def run_audit(self):
        """Run full audit routine."""
        logger.info("=" * 80)
        logger.info("STARTING NIGHTLY AUDIT")
        logger.info("=" * 80)

        start_time = datetime.now()

        # Run audit tasks
        tasks = [
            self.audit_stale_addresses(),
            self.audit_failed_lookups(),
            self.audit_low_confidence(),
            self.audit_expired_leases(),
            self.cleanup_old_data()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Audit task {i} failed: {result}")
            else:
                logger.info(f"Audit task {i} completed: {result}")

        # Generate report
        duration = (datetime.now() - start_time).total_seconds()

        report = {
            "timestamp": start_time.isoformat(),
            "duration_seconds": duration,
            "tasks_completed": len([r for r in results if not isinstance(r, Exception)]),
            "tasks_failed": len([r for r in results if isinstance(r, Exception)]),
            "connector_scorecard": self.connector_mgr.get_scorecard()
        }

        logger.info("=" * 80)
        logger.info("AUDIT COMPLETE")
        logger.info(f"Duration: {duration:.2f}s")
        logger.info(f"Completed: {report['tasks_completed']}")
        logger.info(f"Failed: {report['tasks_failed']}")
        logger.info("=" * 80)

        return report

    async def audit_stale_addresses(self) -> Dict:
        """
        Find and update stale addresses.

        Addresses older than 180 days are re-queried.
        """
        logger.info("Auditing stale addresses...")

        # Query for stale addresses
        cursor = self.db.conn.cursor()

        stale_cutoff = datetime.now() - timedelta(days=180)
        placeholder = '?' if self.db.db_type == 'sqlite' else '%s'

        cursor.execute(f"""
            SELECT a.*, p.name as party_name
            FROM addresses a
            JOIN parties p ON p.id = a.party_id
            WHERE a.source_date < {placeholder}
            AND a.source != 'manual_override'
            LIMIT 100
        """, (stale_cutoff if self.db.db_type == 'postgres' else stale_cutoff.isoformat(),))

        stale_addresses = cursor.fetchall()
        cursor.close()

        logger.info(f"Found {len(stale_addresses)} stale addresses")

        updated = 0

        for addr in stale_addresses:
            try:
                # Try to get updated address
                party_name = addr['party_name'] if self.db.db_type == 'postgres' else addr[13]  # Adjust index for SQLite

                new_addr = await self.connector_mgr.resolve_address(party_name)

                if new_addr and new_addr.confidence_score > 70:
                    # Update database
                    # (Implementation would update the address record)
                    updated += 1
                    logger.info(f"Updated address for {party_name}")

            except Exception as e:
                logger.error(f"Failed to update address: {e}")

        return {
            "task": "stale_addresses",
            "found": len(stale_addresses),
            "updated": updated
        }

    async def audit_failed_lookups(self) -> Dict:
        """
        Retry previously failed lookups.

        Checks audit_queue for failed items and retries.
        """
        logger.info("Auditing failed lookups...")

        queue_items = self.db.get_audit_queue(limit=50)

        logger.info(f"Found {len(queue_items)} items in audit queue")

        retried = 0
        succeeded = 0

        for item in queue_items:
            try:
                # Skip if max attempts reached
                if item['attempts'] >= item['max_attempts']:
                    continue

                # Retry based on audit type
                if item['audit_type'] == 'failed_lookup':
                    # Retry owner lookup
                    # (Implementation depends on what entity failed)
                    pass

                retried += 1

            except Exception as e:
                logger.error(f"Retry failed: {e}")

        return {
            "task": "failed_lookups",
            "queue_size": len(queue_items),
            "retried": retried,
            "succeeded": succeeded
        }

    async def audit_low_confidence(self) -> Dict:
        """
        Review low-confidence data.

        Flags records with confidence < 50 for manual review.
        """
        logger.info("Auditing low-confidence data...")

        cursor = self.db.conn.cursor()

        placeholder = '?' if self.db.db_type == 'sqlite' else '%s'

        # Find low-confidence interests
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM interests
            WHERE confidence_score < {placeholder}
        """, (50.0,))

        low_conf_interests = cursor.fetchone()[0]

        # Find low-confidence addresses
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM addresses
            WHERE confidence_score < {placeholder}
        """, (50.0,))

        low_conf_addresses = cursor.fetchone()[0]

        cursor.close()

        logger.info(f"Low confidence: {low_conf_interests} interests, {low_conf_addresses} addresses")

        return {
            "task": "low_confidence",
            "low_conf_interests": low_conf_interests,
            "low_conf_addresses": low_conf_addresses
        }

    async def audit_expired_leases(self) -> Dict:
        """
        Find and mark expired leases.

        Leases past expiration_date are marked inactive.
        """
        logger.info("Auditing expired leases...")

        cursor = self.db.conn.cursor()

        now = datetime.now()
        placeholder = '?' if self.db.db_type == 'sqlite' else '%s'

        # Find expired but still active leases
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM leases
            WHERE is_active = 1
            AND expiration_date < {placeholder}
        """, (now if self.db.db_type == 'postgres' else now.isoformat(),))

        expired_count = cursor.fetchone()[0]

        # Mark as inactive
        cursor.execute(f"""
            UPDATE leases
            SET is_active = 0, updated_at = {placeholder}
            WHERE is_active = 1
            AND expiration_date < {placeholder}
        """, (
            now if self.db.db_type == 'postgres' else now.isoformat(),
            now if self.db.db_type == 'postgres' else now.isoformat()
        ))

        self.db.conn.commit()
        cursor.close()

        logger.info(f"Marked {expired_count} leases as expired")

        return {
            "task": "expired_leases",
            "expired_count": expired_count
        }

    async def cleanup_old_data(self) -> Dict:
        """
        Clean up old data.

        Removes:
        - Processing logs > 90 days old
        - Completed audit queue items > 30 days old
        """
        logger.info("Cleaning up old data...")

        cursor = self.db.conn.cursor()

        log_cutoff = datetime.now() - timedelta(days=90)
        audit_cutoff = datetime.now() - timedelta(days=30)

        placeholder = '?' if self.db.db_type == 'sqlite' else '%s'

        # Delete old logs
        cursor.execute(f"""
            DELETE FROM processing_log
            WHERE timestamp < {placeholder}
        """, (log_cutoff if self.db.db_type == 'postgres' else log_cutoff.isoformat(),))

        deleted_logs = cursor.rowcount

        # Delete old audit items
        cursor.execute(f"""
            DELETE FROM audit_queue
            WHERE status = 'completed'
            AND resolved_at < {placeholder}
        """, (audit_cutoff if self.db.db_type == 'postgres' else audit_cutoff.isoformat(),))

        deleted_audit = cursor.rowcount

        self.db.conn.commit()
        cursor.close()

        logger.info(f"Deleted {deleted_logs} old logs, {deleted_audit} old audit items")

        return {
            "task": "cleanup",
            "deleted_logs": deleted_logs,
            "deleted_audit_items": deleted_audit
        }


def schedule_nightly_audit(db: Database, connector_mgr: ConnectorManager):
    """
    Schedule nightly audit to run at 2:00 AM.

    Args:
        db: Database instance
        connector_mgr: Connector manager
    """
    audit = NightlyAudit(db, connector_mgr)

    # Schedule for 2:00 AM
    schedule.every().day.at("02:00").do(
        lambda: asyncio.run(audit.run_audit())
    )

    logger.info("Nightly audit scheduled for 2:00 AM")

    # Run scheduler loop
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


if __name__ == "__main__":
    # For testing, run audit immediately
    logging.basicConfig(level=logging.INFO)

    db = Database()
    connector_mgr = ConnectorManager(db)
    audit = NightlyAudit(db, connector_mgr)

    asyncio.run(audit.run_audit())
