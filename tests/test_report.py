import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import report  # noqa: E402


class TestReport(unittest.TestCase):
    def _decision(self):
        return {"status": "Assigned out", "confidence": 0.85, "explanation": "conveyed out"}

    def _docs(self):
        return [{"instrument": "Assignment", "recording_date": "2023-06-01",
                 "grantor": "Rodney G", "grantee": ["Buyer LLC"], "legal_short": "Sec 1 T7N R63W"}]

    def test_render_contains_decision_and_chain(self):
        text = report.render_decision_report("Rodney G", "Sec 1", self._decision(), self._docs())
        self.assertIn("Assigned out", text)
        self.assertIn("0.85", text)
        self.assertIn("Assignment", text)
        self.assertIn("Buyer LLC", text)

    def test_write_report_never_overwrites(self):
        out = Path(tempfile.mkdtemp())
        text = report.render_decision_report("Rodney G", "Sec 1", self._decision(), self._docs())
        p1 = report.write_report(text, "Sec 1", out_dir=out, ts="20260101_000000")
        p2 = report.write_report(text, "Sec 1", out_dir=out, ts="20260101_000000")
        self.assertTrue(p1.exists())
        self.assertNotEqual(p1, p2)
        self.assertIn("_REVIEW_", p2.name)
        self.assertIn("Sec_1", p1.name)


if __name__ == "__main__":
    unittest.main()
