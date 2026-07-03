import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.extractor import ExtractorAgent  # noqa: E402
from agents.reasoner import ReasonerAgent  # noqa: E402
from tools.llm import LLMClient  # noqa: E402


class TestExtractor(unittest.TestCase):
    def test_offline_extract_fields(self):
        text = (
            "Warranty Deed. Document No: 4567890. Recorded: 2024-05-01.\n"
            "Grantor: Alice Smith\n"
            "Grantee: Bob Jones\n"
            "Legal: Sec 1, T7N, R63W"
        )
        agent = ExtractorAgent(outputs_dir=Path("/tmp/dbx_agent_out"))
        data = agent.run(text)
        self.assertEqual(data["instrument"], "Warranty Deed")
        self.assertEqual(data["doc_no"], "4567890")
        self.assertEqual(data["recording_date"], "2024-05-01")
        self.assertEqual(data["grantor"], "Alice Smith")
        self.assertIn("Bob Jones", data["grantee"])
        self.assertEqual(data["legal_short"], "Sec 1 T7N R63W")


class TestReasoner(unittest.TestCase):
    def setUp(self):
        self.agent = ReasonerAgent(outputs_dir=Path("/tmp/dbx_agent_out"))

    def test_current_owner(self):
        docs = [{"instrument": "Warranty Deed", "grantor": "Alice",
                 "grantee": ["Rodney G"], "legal_short": "Sec 1 T7N R63W"}]
        d = self.agent.run(docs, owner="Rodney G")
        self.assertEqual(d["status"], "Current owner of record")

    def test_assigned_out(self):
        docs = [
            {"instrument": "Warranty Deed", "grantor": "Alice", "grantee": ["Rodney G"],
             "legal_short": "Sec 1 T7N R63W"},
            {"instrument": "Assignment", "grantor": "Rodney G", "grantee": ["Buyer LLC"],
             "legal_short": "Sec 1 T7N R63W"},
        ]
        d = self.agent.run(docs, owner="Rodney G")
        self.assertEqual(d["status"], "Assigned out")

    def test_leased_hbp(self):
        docs = [{"instrument": "Oil & Gas Lease", "grantor": "Rodney G",
                 "grantee": ["Operator Co"], "legal_short": "Sec 1 T7N R63W"}]
        d = self.agent.run(docs, owner="Rodney G")
        self.assertEqual(d["status"], "Leased HBP")

    def test_unknown_when_no_section_match(self):
        docs = [{"instrument": "Deed", "grantor": "X", "grantee": ["Rodney G"],
                 "legal_short": "Sec 9 T7N R63W"}]
        d = self.agent.run(docs, owner="Rodney G", section="Sec 1")
        self.assertEqual(d["status"], "Unknown—needs manual")


class TestLLMClientOffline(unittest.TestCase):
    def test_not_live_without_keys(self):
        # No provider keys set in this environment -> not live.
        client = LLMClient("anthropic:claude-3-5-sonnet")
        self.assertFalse(client.is_live)
        with self.assertRaises(RuntimeError):
            client.complete("sys", "user")


if __name__ == "__main__":
    unittest.main()
