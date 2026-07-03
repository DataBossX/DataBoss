import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cli import main  # noqa: E402


class TestCli(unittest.TestCase):
    def test_ingest_csv(self):
        tmp = Path(tempfile.mkdtemp())
        csv = tmp / "n.csv"
        csv.write_text("owner,section\nRodney G,Sec 1\n")
        self.assertEqual(main(["ingest", str(csv)]), 0)

    def test_run_section_writes_report(self):
        tmp = Path(tempfile.mkdtemp())
        docs = tmp / "docs.json"
        docs.write_text(json.dumps([
            {"source": "doc/1", "text": "Warranty Deed. Recorded: 2020-01-01.\n"
                                        "Grantor: Alice\nGrantee: Rodney G\nLegal: Sec 1, T7N, R63W"},
            {"source": "doc/2", "text": "Assignment. Recorded: 2023-06-01.\n"
                                        "Grantor: Rodney G\nGrantee: Buyer LLC\nLegal: Sec 1, T7N, R63W"},
        ]))
        rc = main([
            "run-section", "--owner", "Rodney G", "--section", "Sec 1",
            "--docs", str(docs), "--db", str(tmp / "cli.sqlite"), "--out", str(tmp),
        ])
        self.assertEqual(rc, 0)
        reports = list(tmp.glob("Sec_1_REVIEW_*.md"))
        self.assertEqual(len(reports), 1)
        self.assertIn("Assigned out", reports[0].read_text())


if __name__ == "__main__":
    unittest.main()
