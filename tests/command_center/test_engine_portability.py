"""Engine portability: the same guarantees on SQLite and PostgreSQL.

PostgreSQL is the canonical cloud target (ADR-0003). The whole suite runs on
both engines when ``DBX_CC_TEST_DSN`` is set, but the checks here are explicit
about *why* that matters: they assert the constraint objects that carry the
single-writer invariant actually exist in PostgreSQL, rather than inferring it
from tests happening to pass.
"""

from __future__ import annotations

import unittest

from command_center import db as dbmod
from command_center.slice import run_slice

from .support import POSTGRES_DSN, KernelTestCase


class PlaceholderTranslationTests(unittest.TestCase):
    """``?`` becomes ``$n`` -- and never inside a string literal."""

    def test_simple_placeholders_are_numbered(self):
        self.assertEqual(
            dbmod._to_numbered("SELECT * FROM t WHERE a=? AND b=?"),
            "SELECT * FROM t WHERE a=$1 AND b=$2",
        )

    def test_question_marks_inside_string_literals_are_left_alone(self):
        self.assertEqual(
            dbmod._to_numbered("SELECT '?' AS q, x FROM t WHERE y=?"),
            "SELECT '?' AS q, x FROM t WHERE y=$1",
        )

    def test_escaped_quotes_do_not_break_the_scanner(self):
        self.assertEqual(
            dbmod._to_numbered("SELECT 'it''s ? fine' AS s WHERE a=?"),
            "SELECT 'it''s ? fine' AS s WHERE a=$1",
        )

    def test_statements_without_placeholders_are_unchanged(self):
        sql = "CREATE TABLE t (a TEXT)"
        self.assertEqual(dbmod._to_numbered(sql), sql)


class DialectSelectionTests(unittest.TestCase):
    def test_postgres_dsns_are_recognised(self):
        self.assertTrue(dbmod.is_postgres("postgres://u@h/db"))
        self.assertTrue(dbmod.is_postgres("postgresql://u@h/db"))

    def test_paths_are_treated_as_sqlite(self):
        self.assertFalse(dbmod.is_postgres("/tmp/cc.db"))
        self.assertFalse(dbmod.is_postgres("cc.db"))

    def test_sqlite_takes_the_immediate_write_lock(self):
        self.assertEqual(dbmod.begin_sql(dbmod.DIALECT_SQLITE), "BEGIN IMMEDIATE")
        self.assertEqual(dbmod.begin_sql(dbmod.DIALECT_POSTGRES), "BEGIN")

    def test_both_dialects_produce_the_same_table_set(self):
        def tables(dialect):
            return sorted(
                statement.split("EXISTS")[1].split("(")[0].strip()
                for statement in dbmod.migrations_for(dialect)
                if "CREATE TABLE IF NOT EXISTS" in statement
            )

        self.assertEqual(tables(dbmod.DIALECT_SQLITE), tables(dbmod.DIALECT_POSTGRES))

    def test_every_dialect_declares_the_single_writer_index(self):
        for dialect in (dbmod.DIALECT_SQLITE, dbmod.DIALECT_POSTGRES):
            joined = " ".join(dbmod.migrations_for(dialect))
            self.assertIn("ux_lease_one_active_per_scope", joined)
            self.assertIn("WHERE state = 'ACTIVE'", joined)


@unittest.skipUnless(POSTGRES_DSN, "set DBX_CC_TEST_DSN to run PostgreSQL checks")
class PostgresStructureTests(KernelTestCase):
    """These only run against a real server, and are skipped otherwise.

    Skipped is reported as skipped -- never as passed.
    """

    def _schema(self) -> str:
        return self.kernel.conn.execute("SELECT current_schema() AS s").fetchone()["s"]

    def test_running_on_postgres(self):
        self.assertEqual(self.kernel.conn.dialect, dbmod.DIALECT_POSTGRES)
        version = self.kernel.conn.execute("SELECT version() AS v").fetchone()["v"]
        self.assertIn("PostgreSQL", version)

    def test_all_unique_indexes_exist(self):
        rows = self.kernel.conn.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname=? AND indexname LIKE 'ux_%'",
            (self._schema(),),
        ).fetchall()
        names = {row["indexname"] for row in rows}
        for expected in ("ux_lease_one_active_per_scope", "ux_lease_scope_sequence",
                         "ux_commands_idempotency", "ux_attempt_task_completed"):
            self.assertIn(expected, names)

    def test_single_writer_index_is_genuinely_partial(self):
        """A partial index is what allows many RELEASED rows but one ACTIVE."""
        definition = self.kernel.conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE schemaname=? AND indexname=?",
            (self._schema(), "ux_lease_one_active_per_scope"),
        ).fetchone()["indexdef"]
        self.assertIn("UNIQUE", definition.upper())
        self.assertIn("WHERE", definition.upper())
        self.assertIn("ACTIVE", definition)

    def test_all_protective_triggers_exist(self):
        rows = self.kernel.conn.execute(
            "SELECT tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid"
            " JOIN pg_namespace n ON n.oid = c.relnamespace"
            " WHERE n.nspname = ? AND NOT t.tgisinternal",
            (self._schema(),),
        ).fetchall()
        names = {row["tgname"] for row in rows}
        for expected in ("trg_holds_no_delete", "trg_holds_no_downgrade",
                         "trg_commands_no_transcript_rewrite",
                         "trg_artifact_version_accepted_immutable",
                         "trg_artifact_version_accepted_no_delete",
                         "trg_audit_no_update", "trg_audit_no_delete"):
            self.assertIn(expected, names)

    def test_parameters_are_bound_not_interpolated(self):
        """A classic injection payload must come back as literal text."""
        payload = "'; DROP TABLE holds; --"
        row = self.kernel.conn.execute("SELECT ? AS echoed", (payload,)).fetchone()
        self.assertEqual(row["echoed"], payload)
        self.assertEqual(len(self.kernel.hold_labels()), 4)

    def test_full_vertical_slice_runs_on_postgres(self):
        import shutil
        import tempfile

        workdir = tempfile.mkdtemp(prefix="dbx-cc-pg-slice-")
        self.addCleanup(shutil.rmtree, workdir, True)
        trace = run_slice(workdir, db_target=self.db_path)
        kernel = trace.pop("kernel")
        self.addCleanup(kernel.conn.close)
        summary = trace["summary"]

        self.assertEqual(summary["engine"], dbmod.DIALECT_POSTGRES)
        self.assertEqual(summary["outcome"], "COMPLETED")
        self.assertEqual(summary["execution_mode"], "SIMULATED")
        self.assertTrue(summary["audit_chain_valid"])
        self.assertTrue(summary["idempotent"])
        self.assertTrue(summary["hold_removal_refused"])
        self.assertTrue(summary["drive_readback_verified"])
        for expected in ("Horizon Section 32", "Penterra Section 20", "Penterra Section 17"):
            self.assertIn(expected, summary["holds_preserved"])
        for _name, verdict in summary["watcher_verdicts"]:
            self.assertEqual(verdict, "PASS")


if __name__ == "__main__":
    unittest.main()
