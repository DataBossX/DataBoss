from pathlib import Path
from zipfile import ZipFile

from tools.penterra.document_type_purity import merge_legal, split_document_type
from tools.penterra.image_census import account_paths
from tools.penterra.ods_xml import (
    count_nonempty_table_rows,
    load_content,
    replace_exact_paragraphs,
    write_ods,
)
from tools.penterra.zip_integrity import inspect_package, sha256_file


def test_split_and_merge_keep_qualification_out_of_type():
    clean, qual = split_document_type(
        "Clarification Assignment and Bill of Sale - royalty and ORRI; surface to 100 feet"
    )
    assert clean == "Clarification Assignment and Bill of Sale"
    assert "royalty" in qual
    legal = merge_legal("NE/4 of 11, aol", qual)
    assert legal.startswith("NE/4 of 11, aol;")
    assert clean not in legal or "Clarification" not in legal.split(";")[0]


def test_ods_exact_paragraph_replace(tmp_path: Path):
    src = tmp_path / "src.ods"
    with ZipFile(src, "w") as archive:
        archive.writestr(
            "content.xml",
            (
                '<?xml version="1.0"?>'
                '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
                'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
                'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
                "<office:body><office:spreadsheet><table:table>"
                "<table:table-row><table:table-cell>"
                "<text:p>Transfer of Operating Rights - below base of Example Formation</text:p>"
                "</table:table-cell><table:table-cell><text:p>Lots 1-3</text:p>"
                "</table:table-cell></table:table-row></table:table>"
                "</office:spreadsheet></office:body></office:document-content>"
            ),
        )
        archive.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")

    root = load_content(src)
    changed = replace_exact_paragraphs(
        root,
        {"Transfer of Operating Rights - below base of Example Formation": "Transfer of Operating Rights"},
    )
    assert changed == 1
    dest = tmp_path / "out.ods"
    write_ods(src, dest, root)
    again = load_content(dest)
    assert count_nonempty_table_rows(again) == 1
    xml = ZipFile(dest).read("content.xml").decode("utf-8")
    assert "below base of Example Formation" not in xml
    assert "Transfer of Operating Rights" in xml


def test_zip_integrity_round_trip(tmp_path: Path):
    zpath = tmp_path / "pkg.zip"
    with ZipFile(zpath, "w") as archive:
        archive.writestr("a.txt", "hello")
    report = inspect_package(zpath)
    assert report["crc_pass"] is True
    assert report["member_count"] == 1
    assert report["sha256"] == sha256_file(zpath)


def test_image_census_counts_pdf_pages_not_container(tmp_path: Path):
    pymupdf = __import__("pymupdf")
    pdf = tmp_path / "two.pdf"
    document = pymupdf.open()
    document.new_page()
    document.new_page()
    document.save(pdf)
    document.close()
    result = account_paths([pdf])
    assert result["image_count"] == 2
    assert result["file_count"] == 1
    assert result["pdf_container_extra_images"] == 0
