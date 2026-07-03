import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from init_db import init_db  # noqa: E402


class TestInitDb(unittest.TestCase):
    def test_schema_created_and_idempotent(self):
        tmp = Path(tempfile.mkdtemp()) / "test.sqlite"
        p1 = init_db(tmp)
        self.assertTrue(p1.exists())
        # Running again must not raise or destroy anything.
        init_db(tmp)

        conn = sqlite3.connect(p1)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        finally:
            conn.close()
        self.assertTrue({"documents", "extractions", "audit_log"} <= tables)


if __name__ == "__main__":
    unittest.main()
