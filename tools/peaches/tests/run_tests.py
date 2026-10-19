"""PEACHES engine tests — plain asserts, no pytest dependency.

Builds its own fixtures in a temp dir and exercises: inventory, boundary
detection (text + image-only), index_qa on a county ODS fixture with one
known defect of each asserted kind, donor_compare self-comparison, and
package building with a QA-pattern exclusion.

Run:  python tests/run_tests.py
Exit code 0 only if every check passes.
"""
import json
import os
import sys
import tempfile
import traceback
import zipfile
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

try:
    import pymupdf as _pdf
except ImportError:
    import fitz as _pdf

from peaches import boundaries, donor_compare, index_qa, inventory, package

CHECKS = {"run": 0, "failed": 0}


def check(condition, label):
    CHECKS["run"] += 1
    if condition:
        print("  ok   %s" % label)
    else:
        CHECKS["failed"] += 1
        print("  FAIL %s" % label)


# ---------------------------------------------------------------- fixtures

def make_text_pdf(path, pages=3):
    doc = _pdf.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), "Hello page %d of fixture" % (i + 1))
    doc.save(path)
    doc.close()


def make_blank_pdf(path, pages=3):
    doc = _pdf.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(path)
    doc.close()


def _cell(text):
    if text == "":
        return "<table:table-cell/>"
    return ('<table:table-cell office:value-type="string"><text:p>%s'
            "</text:p></table:table-cell>" % escape(text))


def _row(cells, repeat=None):
    attr = ' table:number-rows-repeated="%d"' % repeat if repeat else ""
    return "<table:table-row%s>%s</table:table-row>" % (
        attr, "".join(_cell(c) for c in cells))


COUNTY = ["Document Type", "Grantor", "Grantee", "Doc No", "Book-Page",
          "Date of Doc", "Rec Date", "Legal Description", "Comments"]

ODS_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
  xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
  office:version="1.2">
 <office:body><office:spreadsheet>
  <table:table table:name="Index">
{rows}
  </table:table>
 </office:spreadsheet></office:body>
</office:document-content>
"""

ODS_STYLES = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
  xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
  office:version="1.2">
 <office:styles>
  <style:default-style style:family="table-cell">
   <style:text-properties style:font-name="Calibri" fo:font-size="11pt"/>
  </style:default-style>
  <style:page-layout style:name="pm1">
   <style:page-layout-properties fo:page-width="11in" fo:page-height="8.5in"
     fo:margin-top="0.3in" fo:margin-right="0.7in" fo:margin-bottom="0.3in"
     fo:margin-left="0.7in" style:print-orientation="landscape"/>
  </style:page-layout>
 </office:styles>
</office:document-styles>
"""

ODS_MANIFEST = """<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
 <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/>
 <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
 <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
</manifest:manifest>
"""


def make_county_ods(path):
    rows = []
    for label in ("County:", "Lands:", "Date:", "Starting Date:",
                  "Date Posted Thru:", "Indexed By:", "Project:"):
        rows.append(_row([label, "fixture"]))
    rows.append(_row([""]))                      # row 8 blank
    rows.append(_row(COUNTY))                    # row 9 headers
    rows.append(_row(["Deed", "Ann A", "Bob B", "12345", "100-200",
                      "1/2/2020", "1/3/2020", "Sec 1", ""]))
    rows.append(_row(["Deed", "Cat C", "Dan D", "12345", "100-200",
                      "2/2/2020", "2/3/2020", "Sec 1", "see notes"]))
    rows.append(_row(["Deed", "Eve E", "Finn F", "99999", "101-5",
                      "UNKNOWN", "2020-01-01", "Sec 2", ""]))
    rows.append(_row([""], repeat=3))            # trailing repeated empties
    content = ODS_CONTENT.format(rows="\n".join(rows))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype",
                    "application/vnd.oasis.opendocument.spreadsheet")
        zf.writestr("content.xml", content)
        zf.writestr("styles.xml", ODS_STYLES)
        zf.writestr("META-INF/manifest.xml", ODS_MANIFEST)


# ---------------------------------------------------------------- tests

def test_inventory_and_boundaries(tmp):
    print("test (a) inventory + boundaries on a 3-page text PDF")
    src = os.path.join(tmp, "a_src")
    os.makedirs(src)
    pdf = os.path.join(src, "fixture.pdf")
    make_text_pdf(pdf, pages=3)
    outdir = os.path.join(tmp, "a_out")
    summary = inventory.run_inventory(src, outdir)
    entry = [f for f in summary["files"] if f["name"] == "fixture.pdf"][0]
    check(entry["pages"] == 3, "inventory pages == 3 (got %r)" % entry["pages"])
    check(entry["native_text_pages"] == 3,
          "native text pages == 3 (got %r)" % entry["native_text_pages"])
    sha1 = inventory.sha256_file(pdf)
    sha2 = inventory.sha256_file(pdf)
    check(sha1 == sha2 == entry["sha256"], "SHA-256 stable across reads")
    check(os.path.exists(os.path.join(outdir, "inventory.csv"))
          and os.path.exists(os.path.join(outdir, "inventory.json")),
          "inventory.csv + inventory.json written")

    rows = boundaries.detect_boundaries(pdf)
    check(len(rows) >= 1 and all(r["confidence"] == "CANDIDATE" for r in rows),
          "text PDF yields CANDIDATE boundary rows (got %d)" % len(rows))
    check(not any("VERIFIED" in (r["status"] + r["confidence"]) for r in rows),
          "no detection is ever labelled VERIFIED")

    blank = os.path.join(src, "blank.pdf")
    make_blank_pdf(blank, pages=3)
    rows = boundaries.detect_boundaries(blank)
    check(len(rows) == 1 and rows[0]["status"] == "NEEDS_VISION_QUEUE"
          and rows[0]["pages_total"] == 3,
          "image-only PDF yields exactly one NEEDS_VISION_QUEUE row")


def test_index_qa(tmp):
    print("test (b) index_qa on county ODS fixture with known defects")
    ods = os.path.join(tmp, "fixture_county.ods")
    make_county_ods(ods)
    result = index_qa.qa_workbook(ods)
    check(result["kind"] == "county", "kind detected as county")
    check(result["schema_match"] is True, "schema matches county headers")
    check(result["row8_blank"] is True, "row 8 blank")
    check(result["data_row_count"] == 3,
          "data rows == 3 (got %r)" % result["data_row_count"])
    check(result["duplicates"]["keys"] == 1,
          "exactly 1 duplicate (Doc No, Book-Page) key (got %r)"
          % result["duplicates"])
    check(result["comments_violations"] == 1,
          "exactly 1 comments violation (got %r)"
          % result["comments_violations"])
    check(result["date_violations"] == 1,
          "exactly 1 date violation (got %r)" % result["date_violations"])
    check(result["census"]["Date of Doc"]["unknown"] == 1,
          "census counts exactly 1 UNKNOWN in Date of Doc (got %r)"
          % result["census"]["Date of Doc"])
    check(result["unknown_total"] == 1,
          "total UNKNOWN == 1 (got %r)" % result["unknown_total"])
    outdir = os.path.join(tmp, "b_out")
    jpath, cpath = index_qa.write_outputs(result, outdir)
    check(os.path.exists(jpath) and os.path.exists(cpath),
          "index_qa json + findings csv written")


def test_donor_compare(tmp):
    print("test (c) donor_compare fixture vs itself")
    ods = os.path.join(tmp, "fixture_county.ods")
    if not os.path.exists(ods):
        make_county_ods(ods)
    result = donor_compare.compare(ods, ods)
    statuses = {p: v["status"] for p, v in result["properties"].items()}
    check(all(s == "AGREES" for s in statuses.values()),
          "self-comparison: all properties AGREES (got %r)" % statuses)
    check(result["properties"]["default_font_name"]["candidate"] == "Calibri",
          "default font read as Calibri (got %r)"
          % result["properties"]["default_font_name"]["candidate"])
    check(result["properties"]["page_orientation"]["candidate"] == "landscape",
          "page orientation read as landscape")


def test_package(tmp):
    print("test (d) package build with QA-pattern exclusion")
    case = os.path.join(tmp, "case_d")
    os.makedirs(case)
    ods = os.path.join(case, "S99_County.ods")
    make_county_ods(ods)
    ledger = os.path.join(case, "QA_ledger.csv")
    with open(ledger, "w") as fh:
        fh.write("internal,qa\n")
    plain = os.path.join(case, "plain.txt")
    with open(plain, "w") as fh:
        fh.write("client-visible note\n")
    manifest = os.path.join(case, "manifest.json")
    with open(manifest, "w") as fh:
        json.dump({"files": [
            {"path": ods, "arcname": "S99_County.ods"},
            {"path": ledger, "arcname": "QA_ledger.csv"},
            {"path": plain, "arcname": "plain.txt"},
        ]}, fh)
    zip_path = os.path.join(case, "client.zip")
    qa_dir = os.path.join(case, "qa_out")
    receipt = package.build_package(manifest, zip_path, qa_dir)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    check("S99_County.ods" in names and "plain.txt" in names,
          "client files present in ZIP (got %r)" % names)
    check("QA_ledger.csv" not in names,
          "QA-pattern file excluded from client ZIP")
    check(len(receipt["excluded"]) == 1
          and receipt["excluded"][0]["arcname"] == "QA_ledger.csv",
          "exclusion recorded in receipt")
    check(receipt["crc_ok"] is True, "ZIP CRC test ok")
    check(os.path.exists(os.path.join(qa_dir, "QA_RECEIPT.json")),
          "QA_RECEIPT.json written to the separate QA dir")
    check(not os.path.exists(os.path.join(case, "QA_RECEIPT.json")),
          "receipt not placed beside the client ZIP")


def main():
    tmp = tempfile.mkdtemp(prefix="peaches_test_")
    print("fixtures in %s" % tmp)
    for fn in (test_inventory_and_boundaries, test_index_qa,
               test_donor_compare, test_package):
        try:
            fn(tmp)
        except Exception:
            CHECKS["failed"] += 1
            print("  FAIL %s raised:" % fn.__name__)
            traceback.print_exc()
    print("checks run: %d, failed: %d" % (CHECKS["run"], CHECKS["failed"]))
    if CHECKS["failed"]:
        print("RESULT: FAILURES PRESENT")
        return 1
    print("RESULT: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
