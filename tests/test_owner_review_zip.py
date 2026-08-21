from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from automation.owner_review_zip import (
    PackagePolicyError,
    build_owner_review_zip,
    inspect_owner_review_zip,
)


class OwnerReviewZipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.turn_in = self.root / "TURN_IN"
        self.turn_in.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, relative: str, content: bytes = b"test") -> Path:
        path = self.turn_in / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_builds_clean_package_from_normal_deliverables(self) -> None:
        self.write("County_Abstract_Index.xlsx", b"xlsx")
        self.write("Abstract_Checklist.xlsx", b"check")
        self.write("Certification_Letter.docx", b"docx")
        self.write("Certification_Letter.pdf", b"pdf")
        output = self.root / "owner_review.zip"

        receipt = build_owner_review_zip(self.turn_in, output)

        self.assertTrue(output.exists())
        self.assertEqual(
            receipt["members"],
            [
                "Abstract_Checklist.xlsx",
                "Certification_Letter.docx",
                "Certification_Letter.pdf",
                "County_Abstract_Index.xlsx",
            ],
        )
        self.assertTrue(receipt["readback_verified"])
        self.assertEqual(inspect_owner_review_zip(output)["members"], receipt["members"])

    def test_rejects_unrecognized_source_pdf_even_inside_turn_in(self) -> None:
        self.write("County_Abstract_Index.xlsx", b"xlsx")
        self.write("0210-0430.pdf", b"source")

        with self.assertRaisesRegex(PackagePolicyError, "unrecognized PDF"):
            build_owner_review_zip(self.turn_in, self.root / "bad.zip")

    def test_rejects_source_named_directories(self) -> None:
        self.write("SOURCE_PDFS/241-190.pdf", b"source")

        with self.assertRaisesRegex(PackagePolicyError, "prohibited source directory"):
            build_owner_review_zip(self.turn_in, self.root / "bad.zip")

    def test_output_is_byte_deterministic(self) -> None:
        self.write("Report.xlsx", b"same")
        self.write("Certification.pdf", b"same-pdf")
        first = self.root / "one.zip"
        second = self.root / "two.zip"

        build_owner_review_zip(self.turn_in, first)
        build_owner_review_zip(self.turn_in, second)

        self.assertEqual(
            hashlib.sha256(first.read_bytes()).hexdigest(),
            hashlib.sha256(second.read_bytes()).hexdigest(),
        )

    def test_explicit_manifest_can_include_known_report_pdf(self) -> None:
        self.write("Owner_Decision_Brief.pdf", b"brief")
        manifest = self.root / "manifest.json"
        manifest.write_text(
            json.dumps({"include": ["Owner_Decision_Brief.pdf"]}),
            encoding="utf-8",
        )

        receipt = build_owner_review_zip(
            self.turn_in,
            self.root / "ok.zip",
            manifest_path=manifest,
        )

        self.assertEqual(receipt["members"], ["Owner_Decision_Brief.pdf"])

    def test_manifest_cannot_escape_turn_in(self) -> None:
        outside = self.root / "outside.pdf"
        outside.write_bytes(b"outside")
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({"include": ["../outside.pdf"]}), encoding="utf-8")

        with self.assertRaisesRegex(PackagePolicyError, "outside TURN_IN"):
            build_owner_review_zip(self.turn_in, self.root / "bad.zip", manifest_path=manifest)

    def test_module_cli_builds_zip_and_receipt(self) -> None:
        self.write("County_Abstract_Index.xlsx", b"xlsx")
        output = self.root / "cli.zip"
        receipt = self.root / "cli.receipt.json"

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "automation.owner_review_zip",
                "--turn-in",
                str(self.turn_in),
                "--output",
                str(output),
                "--receipt",
                str(receipt),
            ],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(output.exists())
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(payload["members"], ["County_Abstract_Index.xlsx"])
        self.assertIn(payload["zip_sha256"], completed.stdout)

    def test_zip_inspector_rejects_path_traversal(self) -> None:
        path = self.root / "unsafe.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("../escape.txt", b"bad")

        with self.assertRaisesRegex(PackagePolicyError, "unsafe member path"):
            inspect_owner_review_zip(path)


if __name__ == "__main__":
    unittest.main()
