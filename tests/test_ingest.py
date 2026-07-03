import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.ingest import load_rows  # noqa: E402


class TestIngest(unittest.TestCase):
    def test_load_csv(self):
        tmp = Path(tempfile.mkdtemp()) / "notice.csv"
        tmp.write_text("doc_no,grantor,section\n123,Alice,Sec 1\n456,Bob,Sec 2\n")
        rows = load_rows(tmp)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["grantor"], "Alice")
        self.assertEqual(rows[1]["section"], "Sec 2")

    def test_unsupported_format(self):
        with self.assertRaises(ValueError):
            load_rows("something.pdf")


if __name__ == "__main__":
    unittest.main()
