import unittest

from tests import fixtures  # noqa: F401  (sets sys.path)
from aqa import checks, census, tables
from aqa.config import load_config
from aqa.reconcile import recorder_identity
from aqa.config import COUNTY_SCHEMA_DEFAULT as COUNTY, FEDERAL_SCHEMA_DEFAULT as FED


def cfg():
    return load_config(None, {"source_roots": ["x"], "output_root": "y"})


class IdentityTests(unittest.TestCase):
    def test_book_page_variants_collapse(self):
        ids = {recorder_identity(s, "C") for s in ("Book 12 Page 345", "Bk 012, Pg 0345", "12/345", "vol. 12 page 345")}
        self.assertEqual(ids, {"c|B12P345"})

    def test_reception_year_seq(self):
        self.assertEqual(recorder_identity("Rec# 2019-0001234", "C"), "c|R2019-1234")
        self.assertEqual(recorder_identity("2019/1234", "C"), "c|R2019-1234")

    def test_unkeyable_is_none_not_guessed(self):
        self.assertIsNone(recorder_identity("see file", "C"))
        self.assertIsNone(recorder_identity("", "C"))
        self.assertIsNone(recorder_identity("12 345 678", "C"))

    def test_county_isolates_identities(self):
        self.assertNotEqual(recorder_identity("1/2", "A"), recorder_identity("1/2", "B"))


class PageRefTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(checks.parse_page_refs("5-7"), ([5, 6, 7], []))
        self.assertEqual(checks.parse_page_refs("pp. 2, 9"), ([2, 9], []))
        nums, bad = checks.parse_page_refs("iv")
        self.assertEqual((nums, bad), ([], ["iv"]))
        self.assertEqual(checks.parse_page_refs("7-5")[1], ["7-5"])


class RowCountTests(unittest.TestCase):
    def test_only_instrument_rows_count(self):
        rows = [
            ["Tract Index for Section"],  # pre-header title
            COUNTY,
            ["1", "T1", "Deed", "A", "B", "2001-01-01", "1/2", "a.pdf", "1"],
            [],
            ["No instruments found"],
            COUNTY,  # repeated header (page break)
            ["2", "T1", "Deed", "C", "D", "2002-01-01", "1/3", "a.pdf", "2"],
            ["Subtotal", "2"],
            ["See narrative"],
            ["x" * 200],
            ["3", "T2", "Lease", "E", "F", "2003-01-01", "1/4", "a.pdf", "3"],
        ]
        r = tables.count_rows(rows, cfg())
        self.assertEqual(r["data_rows"], 3)
        self.assertEqual(r["header_row"], 2)
        self.assertEqual(r["kind_by_header"], "county")
        self.assertEqual(r["excluded"]["repeated_header"], 1)
        self.assertEqual(r["excluded"]["narrative_placeholder"], 3)
        self.assertEqual(r["excluded"]["total_row"], 1)
        self.assertEqual(r["excluded"]["pre_header"], 1)

    def test_sparse_but_real_row_is_kept(self):
        rows = [COUNTY, ["1", "T1", "", "", "", "", "1/2", "", ""]]
        self.assertEqual(tables.count_rows(rows, cfg())["data_rows"], 1)


class SchemaTests(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(checks.test_schema(COUNTY, "county", cfg())["exact"])
        self.assertTrue(checks.test_schema(FED, "federal", cfg())["exact"])
        self.assertEqual(len(COUNTY), 9)
        self.assertEqual(len(FED), 10)

    def test_ten_columns_is_not_county(self):
        r = checks.test_schema(FED, "county", cfg())
        self.assertFalse(r["exact"])
        self.assertTrue(any("column_count" in i for i in r["issues"]))

    def test_case_and_order(self):
        h = list(COUNTY)
        h[0] = h[0].upper()
        self.assertIn("case_only", " ".join(checks.test_schema(h, "county", cfg())["issues"]))
        h = list(COUNTY)
        h[0], h[1] = h[1], h[0]
        self.assertIn("same_columns_wrong_order", checks.test_schema(h, "county", cfg())["issues"])

    def test_forbidden_headers(self):
        self.assertEqual(checks.forbidden_header_hits(FED + ["BLM File No", " comments "], cfg()), ["BLM File No", " comments "])
        self.assertEqual(checks.forbidden_header_hits(FED, cfg()), [])


class RefTests(unittest.TestCase):
    def setUp(self):
        self.cfg = cfg()
        self.idx = checks.PdfIndex([
            {"path": "root0/pdfs/doc_a.pdf", "ext": ".pdf", "sha256": "a", "pdf_pages": 3},
            {"path": "root0/pdfs/doc_a_Part1.pdf", "ext": ".pdf", "sha256": "b", "pdf_pages": 2},
            {"path": "root0/z.zip!/dup.pdf", "ext": ".pdf", "sha256": "c", "pdf_pages": 4},
            {"path": "root0/dup.pdf", "ext": ".pdf", "sha256": "d", "pdf_pages": 5},
        ])

    def codes(self, **row):
        base = {"Source PDF": "doc_a.pdf", "PDF Page": "1"}
        base.update(row)
        return [f["code"] for f in checks.check_row_refs(base, self.idx, self.cfg)]

    def test_valid(self):
        self.assertEqual(self.codes(), [])
        self.assertEqual(self.codes(**{"PDF Page": "1-3"}), [])

    def test_out_of_range_and_zero(self):
        self.assertIn("PAGE_REF_OUT_OF_RANGE", self.codes(**{"PDF Page": "4"}))
        self.assertIn("PAGE_REF_OUT_OF_RANGE", self.codes(**{"PDF Page": "0"}))

    def test_missing_source_and_unparsable(self):
        self.assertIn("SOURCE_PDF_NOT_FOUND", self.codes(**{"Source PDF": "nope.pdf"}))
        self.assertIn("PAGE_REF_UNPARSABLE", self.codes(**{"PDF Page": "iv"}))

    def test_false_part_number(self):
        self.assertEqual(self.codes(**{"Source PDF": "doc_a.pdf", "Instrument Type": "Deed Part 1"}), [])
        self.assertIn("FALSE_PART_NUMBER", self.codes(**{"Instrument Type": "Deed Part 2"}))
        self.assertIn("FALSE_PART_NUMBER", self.codes(**{"Source PDF": "doc_a_Part2.pdf"}))

    def test_ambiguous_copies_flagged(self):
        self.assertIn("SOURCE_PDF_AMBIGUOUS", self.codes(**{"Source PDF": "dup.pdf"}))


class CensusTests(unittest.TestCase):
    def rec(self, f, rows, **kw):
        d = {"file": f, "sha256": f, "table": "T", "kind": "county", "section": "R41", "data_rows": rows,
             "excluded": {"repeated_header": 0, "narrative_placeholder": 0, "total_row": 0}, "mtime_ns": 0}
        d.update(kw)
        return d

    def test_selection_version_and_dup(self):
        a = self.rec("root0/county_R41_v1.xlsx", 10)
        b = self.rec("root0/county_R41_v2.xlsx", 12)
        c = self.rec("root0/copy/county_R41_v2.xlsx", 12, sha256=b["sha256"])
        c["sha256"] = b["sha256"]
        recs = [a, b, c]
        census.select_tables(recs)
        # identical bytes: the first path in sorted order is canonical, the other is a duplicate copy
        self.assertTrue(c["selected"] and not b["selected"] and not a["selected"])
        self.assertEqual(b["duplicate_of"], c["file"])
        self.assertEqual(a["superseded_by"], c["file"])
        again = [dict(x) for x in (c, b, a)]
        census.select_tables(again)
        self.assertEqual({x["file"]: x["selected"] for x in again}, {x["file"]: x["selected"] for x in recs})

    def test_explanation_finds_subset(self):
        a = self.rec("f1", 10)
        b = self.rec("f2", 5, duplicate_of="f1", selected=False, superseded_by=None)
        a.update(selected=True, duplicate_of=None, superseded_by=None)
        ex = census.explain_difference(15, [a, b], 10)
        self.assertEqual(ex["delta_claimed_minus_selected"], 5)
        self.assertIn(["duplicate_file_copies_rows"], ex["candidate_explanations"])
        self.assertEqual(census.explain_difference(99, [a, b], 10)["candidate_explanations"], [["UNEXPLAINED"]])


if __name__ == "__main__":
    unittest.main()
