import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402
from workflows.notice_list_driver import drive  # noqa: E402


class TestDriver(unittest.TestCase):
    def test_drive_processes_rows(self):
        conn = db.connect(Path(tempfile.mkdtemp()) / "d.sqlite")
        rows = [{"owner": "Rodney G", "section": "Sec 1"}]

        corpus = {
            "Sec 1": [
                ("doc/1", "Warranty Deed. Recorded: 2020-01-01.\nGrantor: Alice\n"
                          "Grantee: Rodney G\nLegal: Sec 1, T7N, R63W"),
            ]
        }

        def resolver(row):
            return corpus[row["section"]]

        results = drive(rows, resolver, conn=conn)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["decision"]["status"], "Current owner of record")
        actions = {r[0] for r in conn.execute("SELECT DISTINCT action FROM audit_log")}
        self.assertIn("section_processed", actions)
        conn.close()


if __name__ == "__main__":
    unittest.main()
