"""Synthetic regression cases for local source-page hyperlinks."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from horizon.workbook_qa import _check_evidence_links


class EvidencePageLinksTests(unittest.TestCase):
    def check_link(self, root, target):
        cell = SimpleNamespace(hyperlink=SimpleNamespace(target=target), coordinate="A2")
        sheet = SimpleNamespace(title="Sources", iter_rows=lambda: [(cell,)])
        return _check_evidence_links(SimpleNamespace(worksheets=[sheet]), root)

    def test_relative_pdf_page_fragment_resolves_to_existing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.pdf").write_bytes(b"synthetic fixture")
            self.assertTrue(self.check_link(root, "source.pdf#page=4").passed)

    def test_encoded_filename_and_fragment_resolve(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source one.pdf").write_bytes(b"synthetic fixture")
            self.assertTrue(self.check_link(root, "source%20one.pdf#page=2").passed)

    def test_fragment_does_not_allow_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "outside.pdf").write_bytes(b"synthetic fixture")
            evidence = root / "evidence"
            evidence.mkdir()
            result = self.check_link(evidence, "../outside.pdf#page=1")
            self.assertFalse(result.passed)
            self.assertEqual(result.findings[0].code, "unresolved_evidence_link")

    def test_network_path_is_not_treated_as_local(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(self.check_link(Path(directory), "//server/source.pdf#page=1").passed)


if __name__ == "__main__":
    unittest.main()
