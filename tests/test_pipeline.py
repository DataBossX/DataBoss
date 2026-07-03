import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402
from workflows.extraction_pipeline import run_pipeline  # noqa: E402


class TestPipeline(unittest.TestCase):
    def test_end_to_end_offline_persists_proof(self):
        dbfile = Path(tempfile.mkdtemp()) / "pipe.sqlite"
        conn = db.connect(dbfile)
        docs = [
            ("weld://doc/1", "Warranty Deed. Recorded: 2020-01-01.\n"
                             "Grantor: Alice\nGrantee: Rodney G\nLegal: Sec 1, T7N, R63W"),
            ("weld://doc/2", "Assignment. Recorded: 2023-06-01.\n"
                             "Grantor: Rodney G\nGrantee: Buyer LLC\nLegal: Sec 1, T7N, R63W"),
        ]
        decision = run_pipeline(docs, owner="Rodney G", section="Sec 1", conn=conn)
        self.assertEqual(decision["status"], "Assigned out")

        # Proof persisted: 2 documents, extractions rows, and audit entries.
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0], 2)
        self.assertGreater(conn.execute("SELECT COUNT(*) FROM extractions").fetchone()[0], 0)
        actions = {r[0] for r in conn.execute("SELECT DISTINCT action FROM audit_log")}
        self.assertIn("extracted", actions)
        self.assertIn("decided", actions)
        conn.close()


if __name__ == "__main__":
    unittest.main()
