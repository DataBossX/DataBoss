import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import workbook_review  # noqa: E402
from app.cli import main  # noqa: E402
from workflows.notice_list_driver import make_corpus_resolver  # noqa: E402


class TestCorpusResolver(unittest.TestCase):
    def test_resolves_section_folder(self):
        base = Path(tempfile.mkdtemp())
        (base / "Sec_1").mkdir()
        (base / "Sec_1" / "a.txt").write_text("Deed for Sec 1")
        resolver = make_corpus_resolver(base)
        docs = resolver({"section": "Sec 1"})
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0][1], "Deed for Sec 1")

    def test_missing_section_returns_empty(self):
        resolver = make_corpus_resolver(Path(tempfile.mkdtemp()))
        self.assertEqual(resolver({"section": "Sec 99"}), [])


class TestWorkbookReviewPath(unittest.TestCase):
    def test_review_path_never_equals_source(self):
        src = "/data/Black_Tip.xlsx"
        dest = workbook_review.review_path(src, ts="20260101_000000")
        self.assertNotEqual(str(dest), src)
        self.assertIn("_REVIEW_20260101_000000", dest.name)
        self.assertEqual(dest.suffix, ".xlsx")

    def test_protected_dest_blocked(self):
        with self.assertRaises(PermissionError):
            workbook_review.write_review_workbook(
                r"D:\Desktop\Horizon\book.xlsx", updates=[], out_dir=r"D:\Desktop\Horizon"
            )


class TestRunNoticeListCli(unittest.TestCase):
    def test_batch_writes_summary_and_per_section(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "corpus" / "Sec_1").mkdir(parents=True)
        (tmp / "corpus" / "Sec_1" / "01.txt").write_text(
            "Warranty Deed. Recorded: 2020-01-01.\nGrantor: Alice\n"
            "Grantee: Rodney G\nLegal: Sec 1, T7N, R63W"
        )
        csv = tmp / "notice.csv"
        csv.write_text("owner,section\nRodney G,Sec 1\n")

        rc = main([
            "run-notice-list", "--csv", str(csv), "--corpus", str(tmp / "corpus"),
            "--db", str(tmp / "b.sqlite"), "--out", str(tmp),
        ])
        self.assertEqual(rc, 0)
        self.assertTrue(list(tmp.glob("Sec_1_REVIEW_*.md")))
        summaries = list(tmp.glob("notice_list_summary_REVIEW_*.md"))
        self.assertEqual(len(summaries), 1)
        self.assertIn("Current owner of record", summaries[0].read_text())


if __name__ == "__main__":
    unittest.main()
