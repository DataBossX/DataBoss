import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from report_pipeline import ai_extract, common as C, interests, minixlsx, quarantine_exec, verify  # noqa: E402


class TestMiniXlsx(unittest.TestCase):
    def test_writes_valid_zip_ooxml(self):
        p = Path(tempfile.mkdtemp()) / "t.xlsx"
        minixlsx.write_xlsx(p, ["name", "amount"],
                            [{"name": "Alice", "amount": 0.5}, {"name": "O'Brien & Co", "amount": "2020-0001"}])
        self.assertTrue(p.exists())
        with zipfile.ZipFile(p) as z:
            names = z.namelist()
            self.assertIn("[Content_Types].xml", names)
            self.assertIn("xl/worksheets/sheet1.xml", names)
            sheet = z.read("xl/worksheets/sheet1.xml").decode()
        self.assertIn("Alice", sheet)
        self.assertIn("O'Brien &amp; Co", sheet)   # XML-escaped
        self.assertIn("<v>0.5</v>", sheet)          # numeric cell
        self.assertIn("2020-0001", sheet)           # id kept as text

    def test_col_letters(self):
        self.assertEqual(minixlsx._col_letter(1), "A")
        self.assertEqual(minixlsx._col_letter(27), "AA")


class TestInterests(unittest.TestCase):
    def test_parse_number(self):
        self.assertAlmostEqual(interests.parse_number("3/16"), 0.1875)
        self.assertAlmostEqual(interests.parse_number("12.5%"), 0.125)
        self.assertAlmostEqual(interests.parse_number("1,280"), 1280.0)
        self.assertIsNone(interests.parse_number("n/a"))

    def test_net_and_decimal(self):
        na, note = interests.net_mineral_acres("80", "0.5")
        self.assertEqual(na, 40.0)
        dec, note = interests.decimal_interest(40, 640, "3/16")
        self.assertAlmostEqual(dec, (40 / 640) * 0.1875)

    def test_insufficient_data_flagged_not_guessed(self):
        val, note = interests.net_mineral_acres("80", "")
        self.assertIsNone(val)
        self.assertIn("insufficient_data", note)

    def test_compute_row_mismatch_detection(self):
        row = interests.compute_row(
            {"net_acres": "40", "royalty": "3/16", "decimal_interest": "0.9"},
            unit_acres="640")
        self.assertIn("DECIMAL MISMATCH", row["review_flag"])


class TestAiOffline(unittest.TestCase):
    def test_offline_is_noop_with_audit(self):
        out = C.output_dir(Path(tempfile.mkdtemp()))
        facts = [{"source_file": "/x/doc.txt", "relpath": "doc.txt", "grantor": ""}]
        result = ai_extract.enrich(facts, [{"source_path": "/x/doc.txt", "text_path": ""}], out, C.get_logger("ai"))
        self.assertEqual(result, facts)  # unchanged offline
        audit = C.read_csv(out / "ai_extraction_audit.csv")
        self.assertTrue(audit and audit[0]["status"] == "skipped_offline")


class TestQuarantineExec(unittest.TestCase):
    def test_dry_run_moves_nothing(self):
        root = Path(tempfile.mkdtemp())
        out = C.output_dir(root)
        f = root / "dup.txt"
        f.write_text("data")
        C.write_table(out, "quarantine_plan",
                      ["path", "relpath", "sha256", "reason", "duplicate_of", "proposed_dest", "note", "approved", "generated_at"],
                      [{"path": str(f), "relpath": "dup.txt", "sha256": C.sha256_file(f),
                        "reason": "dup", "duplicate_of": "orig.txt", "proposed_dest": "quarantine/duplicates/dup.txt",
                        "note": "NO DELETE", "approved": "YES", "generated_at": C.now_iso()}])
        quarantine_exec.run(root, out, apply=False, log=C.get_logger("q1"))
        self.assertTrue(f.exists())  # dry-run: original untouched

    def test_apply_moves_and_preserves(self):
        root = Path(tempfile.mkdtemp())
        out = C.output_dir(root)
        f = root / "dup.txt"
        f.write_text("payload")
        sha = C.sha256_file(f)
        C.write_table(out, "quarantine_plan",
                      ["path", "relpath", "sha256", "approved", "note", "generated_at"],
                      [{"path": str(f), "relpath": "dup.txt", "sha256": sha,
                        "approved": "YES", "note": "NO DELETE", "generated_at": C.now_iso()}])
        quarantine_exec.run(root, out, apply=True, log=C.get_logger("q2"))
        moved = root / "quarantine" / "duplicates" / "dup.txt"
        self.assertFalse(f.exists())          # moved, not copied
        self.assertTrue(moved.exists())       # now in quarantine
        self.assertEqual(C.sha256_file(moved), sha)  # integrity preserved
        self.assertTrue((out / "quarantine_manifest.csv").exists())  # reversible record

    def test_refuses_unapproved(self):
        root = Path(tempfile.mkdtemp())
        out = C.output_dir(root)
        f = root / "keep.txt"
        f.write_text("data")
        C.write_table(out, "quarantine_plan", ["path", "relpath", "approved"],
                      [{"path": str(f), "relpath": "keep.txt", "approved": "no"}])
        quarantine_exec.run(root, out, apply=True, log=C.get_logger("q3"))
        self.assertTrue(f.exists())  # not approved -> not moved


class TestVerify(unittest.TestCase):
    def test_flags_missing_source(self):
        out = C.output_dir(Path(tempfile.mkdtemp()))
        C.write_table(out, "file_inventory", ["path"], [{"path": "/x/a.txt"}])
        C.write_table(out, "extracted_facts",
                      ["source_file", "relpath", "confidence", "review_flags", "decimal_interest"],
                      [{"source_file": "", "relpath": "a.txt", "confidence": "0.9", "review_flags": "", "decimal_interest": ""}])
        C.write_table(out, "review_required", ["severity"], [])
        violations = verify.verify(out)
        self.assertTrue(any(v["check"] == "fact_missing_source" for v in violations))


if __name__ == "__main__":
    unittest.main()
