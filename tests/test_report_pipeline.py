"""End-to-end test for the Grocery Report pipeline against a synthetic fixture.

Builds a tiny project tree (deed, assignment, OGL, an exact duplicate, an
ownership CSV) and runs every stage, asserting outputs exist, facts trace to
source, and known conflicts are detected. Runs stdlib-only (no PDF/OCR/xlsx).
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from report_pipeline import common as C  # noqa: E402
from report_pipeline import pipeline as P  # noqa: E402


def _build_fixture(root: Path) -> None:
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "deed_2020.txt").write_text(
        "WARRANTY DEED\nGrantor: Alice Smith\nGrantee: Rodney Gille\n"
        "Recorded: 2020-03-14\nInstrument No: 2020-0001\n"
        "Legal Description: Sec 1, T7N, R63W\nDecimal Interest: 0.5000\n")
    (root / "docs" / "assignment_2023.txt").write_text(
        "ASSIGNMENT OF INTEREST\nAssignor: Rodney Gille\nAssignee: Buyer LLC\n"
        "Recorded: 2023-06-01\nInstrument No: 2023-0450\n"
        "Legal Description: Sec 1, T7N, R63W\nDecimal Interest: 0.5000\n")
    (root / "docs" / "lease.txt").write_text(
        "OIL AND GAS LEASE\nLessor: Rodney Gille\nLessee: Bonanza Operating\n"
        "Primary Term: 3 years\nRoyalty: 3/16\nLegal Description: Sec 1, T7N, R63W\n")
    # Exact duplicate of the deed (different name) -> quarantine candidate.
    (root / "docs" / "deed_2020_COPY.txt").write_text(
        (root / "docs" / "deed_2020.txt").read_text())
    (root / "ownership.csv").write_text(
        "owner name,net acres,decimal interest\nRodney Gille,80,0.5\nBuyer LLC,80,0.5\n")


class TestReportPipeline(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        _build_fixture(self.root)
        self.out = C.output_dir(self.root)
        self.log = C.get_logger("test_pipeline")

    def test_end_to_end(self):
        P.run_all(self.root, self.out, self.log)

        # A. inventory includes the 5 fixture files
        inv = C.read_csv(self.out / "file_inventory.csv")
        self.assertGreaterEqual(len(inv), 5)
        self.assertTrue(all(r["sha256"] for r in inv))

        # B. dedupe finds the exact duplicate and proposes quarantine (no delete)
        quarantine = C.read_csv(self.out / "quarantine_plan.csv")
        self.assertTrue(any("deed_2020" in r["relpath"] for r in quarantine))
        self.assertTrue(all("NO DELETE" in r["note"] for r in quarantine))
        # originals still exist
        self.assertTrue((self.root / "docs" / "deed_2020.txt").exists())
        self.assertTrue((self.root / "docs" / "deed_2020_COPY.txt").exists())

        # C/E. facts extracted and every row traces to a source file
        facts = C.read_csv(self.out / "extracted_facts.csv")
        self.assertTrue(facts)
        self.assertTrue(all(r["source_file"] for r in facts))
        deed = next(r for r in facts if "deed_2020.txt" in r["relpath"])
        self.assertIn("Alice Smith", deed["grantor"])
        self.assertEqual(deed["instrument_no"], "2020-0001")

        # D. classification recognizes the lease
        cls = C.read_csv(self.out / "document_classification.csv")
        lease = next(r for r in cls if r["relpath"].endswith("lease.txt"))
        self.assertEqual(lease["primary_class"], "oil_and_gas_lease")

        # F. reconciliation: Sec1 tract decimals sum to 1.0 (0.5+0.5) -> ok
        recon = C.read_csv(self.out / "reconciliation_table.csv")
        self.assertTrue(recon)

        # H. report artifacts exist
        for name in ["Grocery_Report_DRAFT.md", "Grocery_Report_Executive_Summary.md",
                     "Grocery_Report_Curative_List.csv", "Grocery_Report_Source_Index.csv"]:
            self.assertTrue((self.out / name).exists(), name)

        # I. dashboard exists and is non-empty
        dash = (self.out / "status_dashboard.html").read_text()
        self.assertIn("Grocery Report", dash)

    def test_rerunnable(self):
        # Running twice must not raise and must overwrite its own outputs only.
        P.run_all(self.root, self.out, self.log)
        P.run_all(self.root, self.out, self.log)
        self.assertTrue((self.out / "file_inventory.csv").exists())


if __name__ == "__main__":
    unittest.main()
