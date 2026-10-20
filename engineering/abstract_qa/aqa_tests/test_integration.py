import io
import json
import os
import random
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from aqa_tests import fixtures as fx
from aqa import federal, inventory, pipeline, reconcile, safety, style, tables
from aqa.config import load_config
from aqa.util import sha256_file


try:
    import pypdf  # noqa: F401
    HAVE_PYPDF = True
except ImportError:
    HAVE_PYPDF = False


def tree_hashes(root: Path) -> dict:
    return {str(p.relative_to(root)): sha256_file(p) for p in sorted(root.rglob("*")) if p.is_file()}


def crow(n, tract, rec, pdf="doc_a.pdf", page="1", itype="Deed", grantor="Alpha", grantee="Beta", date="2001-02-03"):
    return fx.county_row(n, tract, itype, grantor, grantee, date, rec, pdf, page)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / "src"
        self.src.mkdir()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def build_tree(self):
        s = self.src
        fx.make_pdf(s / "pdfs" / "doc_a.pdf", 3)
        fx.make_pdf(s / "pdfs" / "doc_a_Part1.pdf", 2)
        # R41 and R43 are different populations that share one recorder identity (1/100)
        fx.make_xlsx(s / "R41" / "county_R41.xlsx", [fx.COUNTY,
            crow(1, "T1", "1/100"), crow(2, "T1", "1/101", page="2"), ["No instruments found"]])
        fx.make_xlsx(s / "R43" / "county_R43.xlsx", [fx.COUNTY,
            crow(1, "T9", "Book 1 Page 100", grantor="ALPHA"),
            crow(2, "T9", "1/102", grantee="Gamma", page="3")])
        fx.make_ods(s / "R10" / "county_R10.ods", [fx.COUNTY, crow(1, "T5", "2/5")])
        fx.make_xlsx(s / "R41" / "federal_R41.xlsx", [fx.FED,
            fx.fed_row("WYW 0123456", "2001-01-01", "Lease", "Fed", "Co A", "T1", 80, "Active", "doc_a.pdf", "1")])
        fx.make_docx(s / "R43" / "federal_R43.docx", [fx.FED,
            fx.fed_row("WYW123456", "2001-01-01", "Lease", "Fed", "Co B", "T9", 80, "Active", "doc_a.pdf", "1")])


class InventoryTests(Base):
    def test_hashes_crc_pages_nested_zip_images(self):
        data = fx.make_pdf(None, 4)
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as z:
            z.writestr("deep/inner.pdf", fx.make_pdf(None, 2))
        with zipfile.ZipFile(self.src / "pack.zip", "w") as z:
            z.writestr("a.pdf", data)
            z.writestr("nested.zip", inner.getvalue())
        fx.make_pdf(self.src / "loose.pdf", 4)
        fx.make_png(self.src / "scan.png")
        cfg = load_config(None, fx.base_config(self.tmp))
        inv = inventory.run_inventory(cfg)
        e = {x["path"]: x for x in inv["entries"]}
        a = e["root0/pack.zip!/a.pdf"]
        self.assertEqual(a["pdf_pages"], 4)
        self.assertEqual(a["sha256"], e["root0/loose.pdf"]["sha256"])  # duplicate copy visible by sha
        self.assertEqual(a["crc32"], f"{zipfile.ZipFile(self.src / 'pack.zip').getinfo('a.pdf').CRC:08x}")
        self.assertEqual(e["root0/pack.zip!/nested.zip!/deep/inner.pdf"]["pdf_pages"], 2)
        self.assertEqual(e["root0/scan.png"]["image_frames"], 1)

    def test_cache_resumes(self):
        fx.make_pdf(self.src / "a.pdf", 1)
        cfg = load_config(None, fx.base_config(self.tmp))
        cp = self.tmp / "cache.jsonl"
        first = inventory.run_inventory(cfg, cp)
        inventory.save_cache(cp, first["cache_records"])
        second = inventory.run_inventory(cfg, cp)
        self.assertEqual((first["cache_misses"], second["cache_hits"], second["cache_misses"]), (1, 1, 0))

    def test_unsafe_zip_member_skipped(self):
        with zipfile.ZipFile(self.src / "evil.zip", "w") as z:
            z.writestr("../escape.pdf", b"x")
        cfg = load_config(None, fx.base_config(self.tmp))
        ent = inventory.run_inventory(cfg)["entries"]
        self.assertTrue(any(e.get("skipped") == "unsafe_member_path" for e in ent))

    def test_corrupt_pdf_uses_fallback_and_reports(self):
        (self.src / "bad.pdf").write_bytes(b"%PDF-1.4\n/Type /Page\n/Type /Page\n/Type /Pages\n")
        cfg = load_config(None, fx.base_config(self.tmp))
        e = inventory.run_inventory(cfg)["entries"][0]
        self.assertEqual((e["pdf_pages"], e["pdf_method"]), (2, "regex_fallback"))
        self.assertTrue(e["errors"])


class ParserTests(Base):
    def test_all_three_formats_give_same_rows(self):
        rows = [fx.COUNTY, crow(1, "T1", "1/2"), ["No instruments found"], crow(2, "T1", "1/3")]
        fx.make_xlsx(self.src / "a.xlsx", rows)
        fx.make_ods(self.src / "a.ods", rows)
        fx.make_docx(self.src / "a.docx", rows)
        cfg = load_config(None, fx.base_config(self.tmp))
        counts = {}
        for ext in (".xlsx", ".ods", ".docx"):
            t, meta = tables.read_tables(ext, (self.src / f"a{ext}").read_bytes())
            self.assertEqual(len(t), 1)
            counts[ext] = tables.count_rows(t[0]["rows"], cfg)["data_rows"]
        self.assertEqual(counts, {".xlsx": 2, ".ods": 2, ".docx": 2})

    def test_ods_entity_bomb_refused(self):
        with zipfile.ZipFile(self.src / "x.ods", "w") as z:
            z.writestr("content.xml", '<?xml version="1.0"?><!DOCTYPE a [<!ENTITY e "x">]><a/>')
        with self.assertRaises(ValueError):
            tables.read_ods((self.src / "x.ods").read_bytes())


class ReconcileTests(Base):
    def rows(self):
        def r(sec, n, tract, rec, **kw):
            f = dict(zip(fx.COUNTY, crow(n, tract, rec, **kw)))
            return {"section": sec, "county": "Example", "kind": "county", "file": f"{sec}.xlsx", "table": "T",
                    "row_no": n + 1, "fields": f, "selected": True}
        return [
            r("R41", 1, "T1", "1/100"), r("R41", 2, "T1", "1/101"),
            r("R43", 1, "T9", "Book 1 Page 100", grantor="ALPHA"),   # same identity, case-only difference -> agree
            r("R43", 2, "T9", "1/102"),
            r("R43", 3, "T1", "1/101", grantee="Different"),          # same identity as R41 row 2, real conflict
            r("R41", 3, "T1", "1/100"),                               # true in-section duplicate
            r("R41", 4, "T1", "garbled"),                             # no identity
        ]

    def test_results(self):
        cfg = load_config(None, fx.base_config(self.tmp))
        out = reconcile.reconcile(self.rows(), cfg)
        keys = {i["identity"]: i for i in out["identities"]}
        self.assertEqual(set(keys), {"example|B1P100", "example|B1P101", "example|B1P102"})
        rep = {r["identity"]: r for r in out["repetitions"]}
        self.assertTrue(rep["example|B1P100"]["fields_agree"])
        self.assertEqual(rep["example|B1P100"]["classification"], "legitimate_cross_section_repetition")
        self.assertEqual(rep["example|B1P101"]["classification"], "repetition_with_field_conflict")
        self.assertEqual([c["identity"] for c in out["conflicts"]], ["example|B1P101"])
        self.assertEqual(out["conflicts"][0]["conflicts"][0]["field"], "Grantee")
        self.assertEqual(len(out["within_section_duplicates"]), 1)
        self.assertEqual(len(out["no_identity_rows"]), 1)
        miss = {(m["identity"], m["missing_in"]): m["classification"] for m in out["candidate_missing"]}
        self.assertEqual(miss[("example|B1P102", "R41")], "may_be_legitimate_tract_not_in_section")
        self.assertEqual(miss[("example|B1P101", "R43")] if ("example|B1P101", "R43") in miss else None, None)
        self.assertTrue(out["branch_divergence"])

    def test_row_order_cannot_change_result(self):
        cfg = load_config(None, fx.base_config(self.tmp))
        base = reconcile.reconcile(self.rows(), cfg)
        rows = self.rows()
        random.Random(7).shuffle(rows)
        shuf = reconcile.reconcile(rows, cfg)
        for k in ("identities", "repetitions", "candidate_missing", "populations", "branch_divergence"):
            self.assertEqual(base[k], shuf[k], k)
        self.assertEqual([c["identity"] for c in base["conflicts"]], [c["identity"] for c in shuf["conflicts"]])

    def test_probable_omission_when_section_has_the_tract(self):
        cfg = load_config(None, fx.base_config(self.tmp))
        rows = self.rows()
        out = reconcile.reconcile(rows, cfg)
        # R41 holds tract T1; identity 1/101 appears in R43 under T1 -> R41 has it. Remove from R41:
        rows = [r for r in rows if not (r["section"] == "R41" and r["fields"]["Recorder ID"] == "1/101")]
        out = reconcile.reconcile(rows, cfg)
        m = [x for x in out["candidate_missing"] if x["identity"] == "example|B1P101" and x["missing_in"] == "R41"]
        self.assertEqual(m[0]["classification"], "probable_omission_same_tract_present")


class FederalTests(Base):
    def test_ledger_merges_consistent_and_flags_conflict(self):
        cfg = load_config(None, fx.base_config(self.tmp))
        def r(sec, serial, assignee, date="2001-01-01"):
            return {"section": sec, "kind": "federal", "file": sec, "row_no": 2, "fields":
                    dict(zip(fx.FED, fx.fed_row(serial, date, "Lease", "Fed", assignee, "T1", 80, "Active", "d.pdf", "1")))}
        led = federal.build_ledger([r("R41", "WYW 0123456", "Co A"), r("R43", "WYW123456", "Co A"),
                                    r("R45", "WYW 999", "Co A"), r("R46", "WYW 999", "Co Z"),
                                    r("R47", "WYW 999", "Co A", date="2002-02-02"), r("R47", "none", "x")], cfg)
        by = {e["serial"] + e["fields"]["Event Date"]: e for e in led["ledger"]}
        a = by["WYW1234562001-01-01"]
        self.assertEqual((a["status"], a["sections"], a["appearances"]), ("CONSISTENT_ACROSS_SECTIONS", ["R41", "R43"], 2))
        b = by["WYW9992001-01-01"]
        self.assertEqual(b["status"], "NEEDS_IMAGE_REVIEW")
        self.assertEqual(b["fields"]["Assignee"], "")           # never picks a winner
        self.assertIn("Assignee", b["conflicts"])
        self.assertEqual(len(led["unparsed_serial_rows"]), 1)
        self.assertEqual(led["possible_date_conflicts"][0]["serial"], "WYW999")


class StyleTests(Base):
    def test_donor_deviation_and_override(self):
        def rec(sec, ext, hdr):
            return {"file": f"root0/{sec}/county_{sec}.{ext}", "section": sec, "ext": f".{ext}", "kind": "county",
                    "table": "Index", "header": hdr, "file_meta": {"sheets": ["Index"], "format": {"Index": {"header_bold": sec == "R41"}}}}
        recs = [rec("R41", "xlsx", fx.COUNTY), rec("R43", "xlsx", fx.COUNTY), rec("R10", "ods", fx.COUNTY)]
        cfg = load_config(None, fx.base_config(self.tmp, owner_overrides={"R10": {"allow": ["ext", "xlsx_header_bold"]}}))
        out = {s["section"]: s for s in style.compare_to_donor(recs, cfg)["sections"]}
        self.assertEqual([d["key"] for d in out["R43"]["deviations"]], ["xlsx_header_bold"])
        self.assertEqual(out["R43"]["deviations"][0]["state"], "unexplained")
        self.assertTrue(all(d["state"] == "owner_override" for d in out["R10"]["deviations"]))
        self.assertEqual(out["R41"]["deviations"], [])


class SafetyTests(Base):
    def test_output_inside_source_refused_and_nothing_created(self):
        cfg = load_config(None, fx.base_config(self.tmp, output_root=str(self.src / "out")))
        res = pipeline.execute(cfg)
        self.assertEqual(res["status"], "REFUSED")
        self.assertFalse((self.src / "out").exists())

    def test_cloud_output_blocked(self):
        cfg = load_config(None, fx.base_config(self.tmp, output_root=str(self.tmp / "OneDrive - Co" / "out")))
        codes = [f["code"] for f in safety.preflight(cfg)]
        self.assertIn("OUTPUT_IN_CLOUD_SYNC", codes)

    def test_protected_path(self):
        prot = self.tmp / "client_indexes"
        prot.mkdir()
        cfg = load_config(None, fx.base_config(self.tmp, protected_paths=[str(prot)], output_root=str(prot / "sub")))
        self.assertIn("OUTPUT_OVERLAPS_PROTECTED", [f["code"] for f in safety.preflight(cfg)])

    def test_missing_source_root(self):
        shutil.rmtree(self.src)
        cfg = load_config(None, fx.base_config(self.tmp))
        self.assertIn("SOURCE_ROOT_MISSING", [f["code"] for f in safety.preflight(cfg)])

    def test_manifest_compare_and_expected(self):
        prev = [{"path": "a", "sha256": "1"}, {"path": "b", "sha256": "2"}, {"path": "c", "sha256": "3"}]
        cur = [{"path": "a", "sha256": "1"}, {"path": "b", "sha256": "X"}, {"path": "d", "sha256": "4"}]
        codes = sorted(f["code"] for f in safety.compare_manifests(prev, cur))
        self.assertEqual(codes, ["SOURCE_CHANGED", "SOURCE_DISAPPEARED", "SOURCE_NEW"])
        exp = safety.check_expected([{"path": "zz", "sha256": "4"}, {"path": "a", "sha256": "9"}], cur)
        self.assertEqual(sorted(f["code"] for f in exp), ["EXPECTED_SOURCE_HASH_MISMATCH", "EXPECTED_SOURCE_MISSING"])
        self.assertEqual(exp[1]["found_elsewhere"] if exp[1]["code"] == "EXPECTED_SOURCE_MISSING" else exp[0]["found_elsewhere"], ["d"])

    def test_sync_conflict_names(self):
        self.assertTrue(safety.classify_name("x/report (conflicted copy 2024).xlsx"))
        self.assertTrue(safety.classify_name("x/~$lock.xlsx"))
        self.assertFalse(safety.classify_name("x/county_R41.xlsx"))

    def test_guard_refuses_outside_run_dir(self):
        g = safety.OutputGuard(self.tmp / "run", [], [str(self.src)])
        with self.assertRaises(PermissionError):
            g.check(self.src / "x.json")
        with self.assertRaises(PermissionError):
            g.check(self.tmp / "elsewhere.json")
        g.check(self.tmp / "run" / "final" / "x.json")

    def test_write_new_refuses_overwrite(self):
        from aqa.util import write_new_text
        p = self.tmp / "o.txt"
        write_new_text(p, "a")
        with self.assertRaises(FileExistsError):
            write_new_text(p, "b")
        self.assertEqual(p.read_text(), "a")


class EndToEndTests(Base):
    def test_full_run_blocked_with_evidence_sources_untouched_and_resumable(self):
        self.build_tree()
        # inject faults: schema column missing in R11, forbidden header, bad page, false part
        fx.make_xlsx(self.src / "R11" / "county_R11.xlsx", [fx.COUNTY[:8] + ["Comments"], ["1", "T1", "Deed", "A", "B", "2001", "3/3", "doc_a.pdf", "9"]])
        fx.make_xlsx(self.src / "R45" / "county_R45.xlsx", [fx.COUNTY, crow(1, "T1", "5/5", page="9", itype="Deed Part 7")])
        before = tree_hashes(self.src)
        cfg = load_config(None, fx.base_config(self.tmp, claimed_placements=15))
        res = pipeline.execute(cfg, run_id="r1")
        self.assertEqual(res["status"], "BLOCKED")
        self.assertEqual(tree_hashes(self.src), before, "sources must be byte-identical after the run")
        fd = Path(res["final_dir"])
        for name in ("qa_dashboard.html", "qa_receipt.json", "federal_ledger.csv", "reconciliation.json", "census.json", "inventory.csv"):
            self.assertTrue((fd / name).exists(), name)
        self.assertEqual(pipeline.verify_receipt(fd), [])
        secs = {s["section"]: s for s in res["sections"]}
        self.assertTrue(secs["R11"]["schema_not_exact"] and secs["R11"]["forbidden"])
        self.assertTrue(secs["R45"]["page_ref_problems"] and secs["R45"]["false_parts"])
        self.assertEqual(secs["R41"]["data_rows"], 3)  # 2 county + 1 federal; narrative placeholder excluded
        self.assertEqual(secs["R41"]["pdf_files"], 0)
        u = res["units"]
        self.assertEqual(u["pdf_file_copies"], 2)
        self.assertEqual(u["physical_pages_distinct_pdfs"], 5)
        self.assertEqual(u["federal_events"], 1)
        self.assertEqual(u["recorder_identities"], 6)
        ex = res["explanation"]
        self.assertEqual(ex["recalculated_selected"], u["index_placements_total"])
        led = json.loads((fd / "federal_ledger.json").read_text())["ledger"][0]
        self.assertEqual(led["status"], "NEEDS_IMAGE_REVIEW")  # Co A vs Co B never auto-resolved
        # dashboard never claims completion
        html = (fd / "qa_dashboard.html").read_text()
        self.assertNotIn("COMPLETE<", html)
        # tamper detection
        with open(fd / "census.json", "a") as fh:
            fh.write(" ")
        self.assertEqual(pipeline.verify_receipt(fd), ["hash mismatch census.json"])
        # same run id again: refused, nothing overwritten
        with self.assertRaises(FileExistsError):
            pipeline.execute(cfg, run_id="r1")
        # resume reuses every stage and does not rewrite the final dir
        res2 = pipeline.execute(cfg, run_id="r1", resume=True)
        self.assertEqual(res2["final_dir"], res["final_dir"])
        self.assertTrue(res2.get("reused_final"))

    def test_source_change_between_runs_is_flagged(self):
        self.build_tree()
        cfg = load_config(None, fx.base_config(self.tmp))
        pipeline.execute(cfg, run_id="r1")
        (self.src / "R10" / "county_R10.ods").unlink()
        fx.make_pdf(self.src / "pdfs" / "doc_a.pdf", 4)  # same path, different bytes
        res = pipeline.execute(cfg, run_id="r2")
        codes = {f["code"] for f in json.loads((Path(res["final_dir"]) / "safety.json").read_text())}
        self.assertTrue({"SOURCE_DISAPPEARED", "SOURCE_CHANGED"} <= codes)
        self.assertEqual(res["status"], "BLOCKED")

    @unittest.skipUnless(HAVE_PYPDF, "clean PDF page counts require pypdf; fallback counting is flagged as an error by design")
    def test_clean_package_is_clear_but_never_complete(self):
        s = self.src
        fx.make_pdf(s / "doc_a.pdf", 3)
        fx.make_xlsx(s / "R41" / "county_R41.xlsx", [fx.COUNTY, crow(1, "T1", "1/100", page="2")])
        fx.make_xlsx(s / "R41" / "federal_R41.xlsx", [fx.FED, fx.fed_row("WYW 5", "2001-01-01", "Lease", "F", "C", "T1", 1, "A", "doc_a.pdf", "3")])
        cfg = load_config(None, fx.base_config(self.tmp, branch_groups={}, claimed_placements=2,
                                              expected_sources=[{"path": "root0/doc_a.pdf", "sha256": sha256_file(s / "doc_a.pdf")}]))
        res = pipeline.execute(cfg, run_id="clean")
        self.assertEqual(res["status"], "AUTOMATED_CHECKS_CLEAR_IMAGE_REVIEW_PENDING", [x for x in res["sections"] if x["blockers"]])
        self.assertEqual(res["explanation"]["candidate_explanations"], [["exact_match_no_difference"]])

    def test_cli(self):
        from aqa.__main__ import main
        self.build_tree()
        cfgp = self.tmp / "cfg.json"
        cfgp.write_text(json.dumps(fx.base_config(self.tmp)))
        self.assertEqual(main(["run", "--config", str(cfgp), "--run-id", "cli1"]), 2)
        self.assertEqual(main(["run", "--config", str(cfgp), "--run-id", "cli1"]), 1)  # overwrite refused


if __name__ == "__main__":
    unittest.main()
