"""Deterministic tests for the Penterra verification toolkit.

All fixtures are synthetic. No canonical source file is read or modified.
Runs under pytest (CI) and standalone (`python3 penterra/tests/test_tools.py`).
"""
import hashlib
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from tools.stable_key import (  # noqa: E402
    StableKeyError, TractEntry, dedupe, normalize_bookpage, stable_key,
)
from tools.identity import (  # noqa: E402
    SourceFile, candidate_keys, key_from_filename, match_sources,
)
from tools.pdf_census import (  # noqa: E402
    census, count_pages, is_srp, parse_part, parse_serial,
)
from tools.dupe_pages import find_duplicate_pages  # noqa: E402
from tools import blanks  # noqa: E402
from tools.parity import ParityViolation, compare  # noqa: E402
from tools.package import verify_package  # noqa: E402
from tools.replay import Rejection, ReplayDetected  # noqa: E402
from tools.replay import check as replay_check  # noqa: E402
from tools.lease import CollisionError, LeaseStore  # noqa: E402

# The authenticated federal source inventory: (filename, physical pages).
FEDERAL_SOURCES = [
    ("WYW-5955.pdf", 243),
    ("Serial Register Page WYW-5955 (8.4.2026).pdf", 3),
    ("WYW-47318 Part 1 of 4.pdf", 189),
    ("WYW-47318 Part 2 of 4.pdf", 177),
    ("WYW-47318 Part 3 of 4.pdf", 94),
    ("WYW-47318 Part 4 of 4.pdf", 2),
    ("Serial Register Page WYW-47318 (8.04.2026).pdf", 5),
    ("WYW-51704 Part 1 of 6.pdf", 225),
    ("WYW-51704 Part 2 of 6.pdf", 184),
    ("WYW-51704 Part 3 of 6.pdf", 239),
    ("WYW-51704 Part 4 of 6.pdf", 168),
    ("WYW-51704 Part 5 of 6.pdf", 131),
    ("WYW-51704 Part 6 of 6.pdf", 2),
    ("Serial Register Page WYW-51704 (8.04.2026).pdf", 11),
]


# --------------------------------------------------------------- stable_key
def test_stable_key_forms():
    assert stable_key("1063795", "3269-0038") == "1063795|3269-0038"
    assert stable_key("2023-00118", None) == "2023-00118|"
    assert stable_key(None, "0098-0131") == "|0098-0131"
    assert stable_key("#0407085", "25MR-0347") == "407085|25MR-0347"
    assert stable_key("1218", "005M-0119") == "1218|005M-0119"


def test_stable_key_preserves_alpha_book_suffix():
    assert normalize_bookpage("005M-0119") == "005M-0119"
    assert normalize_bookpage("25MR-0347") == "25MR-0347"
    assert normalize_bookpage("02PM-0099") == "02PM-0099"


def test_stable_key_refuses_empty_identity():
    with pytest.raises(StableKeyError):
        stable_key(None, None)


def test_dedupe_names_every_overlap():
    raw = [TractEntry(page=1, row=i, docno=str(1000 + i)) for i in range(1, 46)]
    raw += [
        TractEntry(page=12, row=1, docno="1001", source="typed"),
        TractEntry(page=12, row=2, docno="1002", source="typed"),
        TractEntry(page=12, row=3, docno="9999", source="typed"),
    ]
    by_key, overlaps = dedupe(raw)
    assert len(raw) == 48
    assert len(by_key) == 46
    assert overlaps == ["1001|", "1002|"]
    # The invariant the 461-key ledger depends on.
    assert len(raw) - len(by_key) == len(overlaps)


# ----------------------------------------------------------------- identity
def test_filename_identity_parsing():
    assert key_from_filename("#2023-00118.pdf") == "2023-00118|"
    assert key_from_filename("3305-0366.pdf") == "|3305-0366"
    assert key_from_filename("25MR-0347.pdf") == "|25MR-0347"
    assert key_from_filename("1063795.pdf") == "1063795|"
    assert key_from_filename("random_notes.pdf") is None


def test_ambiguous_stem_emits_both_candidates():
    # A Campbell book numbered 2023 is possible, so dddd-dddd is not decidable
    # from the filename alone. The tool must offer both readings, never guess.
    assert candidate_keys("2023-0366.pdf") == ["2023-0366|", "|2023-0366"]


def test_ambiguity_resolved_by_index_membership():
    res = match_sources(
        [SourceFile("3305-0366.pdf"), SourceFile("#2023-00118.pdf")],
        {"|3305-0366", "2023-00118|"},
    )
    assert res["matched_count"] == 2
    assert res["unmatched"] == []


def test_true_ambiguity_is_dispositioned_not_guessed():
    res = match_sources([SourceFile("2023-0366.pdf")], {"2023-0366|", "|2023-0366"})
    assert res["unmatched"][0]["disposition"] == "AMBIGUOUS"


def test_match_sources_dispositions_and_gaps():
    index = {"2023-00118|", "1063795|3269-0038", "|0098-0131", "555|"}
    res = match_sources(
        [
            SourceFile("#2023-00118.pdf"),
            SourceFile("1063795.pdf"),
            SourceFile("junk.pdf"),
            SourceFile("#2099-00001.pdf"),
            SourceFile("1063795.pdf"),
        ],
        index,
    )
    assert res["matched_count"] == 2
    assert {u["disposition"] for u in res["unmatched"]} == {
        "UNDETERMINED", "NON_INDEX", "DUPLICATE",
    }
    assert res["index_keys_without_source"] == ["555|", "|0098-0131"]


# --------------------------------------------------------------- pdf_census
def test_part_and_serial_parsing():
    assert parse_part("WYW-51704 Part 3 of 6.pdf") == (3, 6)
    assert parse_serial("WYW-5955.pdf") == "WYW-005955"
    assert parse_serial("WYW-47318 Part 1 of 4.pdf") == "WYW-047318"
    assert is_srp("Serial Register Page WYW-5955 (8.4.2026).pdf")
    assert not is_srp("WYW-5955.pdf")


@pytest.mark.parametrize(
    "serial,files,pages",
    [("WYW-005955", 1, 243), ("WYW-047318", 4, 462), ("WYW-051704", 6, 949)],
)
def test_per_serial_casefile_census(serial, files, pages):
    c = census(FEDERAL_SOURCES)["by_serial"][serial]
    assert (c.casefile_files, c.casefile_pages) == (files, pages)


def test_federal_totals_keep_srp_separate():
    c = census(FEDERAL_SOURCES)
    assert (c["casefile_files"], c["casefile_pages"]) == (11, 1654)
    assert (c["srp_files"], c["srp_pages"]) == (3, 19)
    assert (c["total_files"], c["total_pages"]) == (14, 1673)
    assert c["problems"] == []


def test_census_detects_duplicate_part():
    bad = census(FEDERAL_SOURCES + [("WYW-51704 Part 3 of 6.pdf", 239)])
    assert any("duplicate Part 3" in p.get("problem", "") for p in bad["problems"])


def test_census_detects_missing_part():
    gap = census([("WYW-47318 Part 1 of 4.pdf", 189), ("WYW-47318 Part 3 of 4.pdf", 94)])
    assert any("missing Part" in p.get("problem", "") for p in gap["problems"])


def test_count_pages_against_a_real_pdf(tmp_path):
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R 4 0 R 5 0 R] /Count 3 >>",
    ] + ["<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>"] * 3
    body, offsets = "%PDF-1.4\n", []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(body))
        body += f"{i} 0 obj\n{obj}\nendobj\n"
    start = len(body)
    body += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n"
    body += "".join(f"{o:010d} 00000 n \n" for o in offsets)
    body += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n"
    pdf = tmp_path / "three_pages.pdf"
    pdf.write_text(body)

    result = count_pages(pdf)
    assert result["pages"] == 3
    assert result["declared"] == 3
    assert result["agree"]


# -------------------------------------------------------------- dupe_pages
def test_duplicate_pages_split_cross_and_intra_file():
    res = find_duplicate_pages([
        ("a.pdf", 1, b"X"), ("b.pdf", 1, b"X"),
        ("a.pdf", 2, b"Y"), ("a.pdf", 3, b"Y"),
        ("c.pdf", 1, b"Z"),
    ])
    assert len(res["cross_file_duplicates"]) == 1
    assert len(res["intra_file_duplicates"]) == 1
    assert res["unique_pages"] == 3
    assert res["total_pages"] == 5


# ------------------------------------------------------------------ blanks
@pytest.mark.parametrize(
    "field,doc_type,kwargs,expected",
    [
        ("Book-Page", "Corner Record", {"docno": "2026-00020"}, blanks.INAPPLICABLE),
        ("Grantor", "Corner Record", {"docno": "2026-00020"}, blanks.INAPPLICABLE),
        ("Legal Description", "UCC Financing Statement", {}, blanks.INTENTIONAL),
        ("Legal Description", "Warranty Deed", {"has_source": False}, blanks.SOURCE_MISSING),
        ("Date of Doc", "Warranty Deed", {"legible": False}, blanks.UNREADABLE),
        ("Date of Doc", "Warranty Deed", {}, blanks.TRUE_HOLD),
    ],
)
def test_blank_classification(field, doc_type, kwargs, expected):
    klass, reason = blanks.classify(field, doc_type, **kwargs)
    assert klass == expected
    assert reason


def test_blank_census_partitions_exactly():
    cells = [
        {"field": "Grantor", "doc_type": "Corner Record", "docno": "2026-00020"},
        {"field": "Date of Doc", "doc_type": "Warranty Deed", "docno": "1", "legible": False},
    ]
    cen = blanks.census(cells)
    assert cen["total"] == 2
    assert cen["counts"][blanks.UNREADABLE] == 1
    # No cell may be lost or double-counted.
    assert sum(cen["counts"].values()) == cen["total"]


# ------------------------------------------------------------------ parity
def test_parity_matches_identical_presentation():
    res = compare(
        {"font_name": "Calibri", "orientation": "landscape", "print_area": "A1:J198"},
        {"font_name": "Calibri", "orientation": "landscape", "print_area": "A1:J198"},
    )
    assert res["parity"]
    assert res["compared"] == 3


def test_parity_detects_format_difference():
    res = compare({"font_name": "Calibri"}, {"font_name": "Arial"})
    assert not res["parity"]
    assert len(res["differences"]) == 1


def test_parity_does_not_inherit_donor_defects():
    res = compare(
        {"orientation": "landscape"}, {"orientation": "portrait"},
        known_donor_defects={"orientation"},
    )
    assert res["parity"]
    assert len(res["skipped_donor_defects"]) == 1


def test_parity_blocks_copying_facts_from_section_15():
    with pytest.raises(ParityViolation):
        compare({"county_rows": 62}, {"county_rows": 155})


# ----------------------------------------------------------------- package
@pytest.fixture
def sample_package(tmp_path):
    members = {"a.ods": b"AAA", "b.xlsx": b"BBB", "c.docx": b"CCC"}
    path = tmp_path / "pkg.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for name, blob in members.items():
            zf.writestr(name, blob)
    return path, members


def test_package_exact_membership_crc_and_member_hashes(sample_package):
    path, members = sample_package
    want = {n: hashlib.sha256(b).hexdigest() for n, b in members.items()}
    res = verify_package(path, list(members), expected_member_sha=want)
    assert res["pass"]
    assert res["crc_pass"]
    assert res["member_count"] == 3


def test_package_detects_extra_member(sample_package):
    path, _ = sample_package
    res = verify_package(path, ["a.ods", "b.xlsx"])
    assert not res["pass"]
    assert any("unexpected members" in e for e in res["errors"])


def test_package_detects_container_hash_drift(sample_package):
    path, members = sample_package
    res = verify_package(path, list(members), expected_sha256="deadbeef")
    assert not res["pass"]
    assert any("container sha mismatch" in e for e in res["errors"])


def test_package_detects_member_order_drift(sample_package):
    path, _ = sample_package
    res = verify_package(path, ["c.docx", "b.xlsx", "a.ods"], ordered=True)
    assert not res["pass"]


def test_package_fails_closed_when_absent(tmp_path):
    assert verify_package(tmp_path / "nope.zip", [])["pass"] is False


# ------------------------------------------------------------------ replay
REJECTIONS = [
    Rejection("G11", "date", "1989-07-06", "superseded by authenticated floor", "V11.12"),
]


def test_accepted_value_is_not_a_replay():
    assert replay_check({("G11", "date"): "1989-07-08"}, REJECTIONS)["clean"]


def test_detects_reasserted_rejected_value():
    res = replay_check({("G11", "date"): "1989-07-06"}, REJECTIONS)
    assert res["replay_count"] == 1


def test_strict_mode_raises_on_replay():
    with pytest.raises(ReplayDetected):
        replay_check({("G11", "date"): "1989-07-06"}, REJECTIONS, strict=True)


# ------------------------------------------------------------------- lease
TARGET = "45N-76W-11_county.ods"


def test_lease_admits_exactly_one_writer(tmp_path):
    store = LeaseStore(tmp_path)
    lease = store.acquire(TARGET, "claude", preimage_sha256="df7b994b")
    assert lease.fence == 1
    assert store.writer_count(TARGET) == 1
    with pytest.raises(CollisionError):
        store.acquire(TARGET, "codex-pc")
    # Same writer re-acquiring renews without bumping the fence.
    assert store.acquire(TARGET, "claude").fence == 1


def test_guard_commit_enforces_holder_and_preimage(tmp_path):
    store = LeaseStore(tmp_path)
    store.acquire(TARGET, "claude", preimage_sha256="df7b994b")
    store.guard_commit(TARGET, "claude", fence=1, preimage_sha256="df7b994b")
    with pytest.raises(CollisionError):
        store.guard_commit(TARGET, "claude", fence=1, preimage_sha256="OTHER")
    with pytest.raises(CollisionError):
        store.guard_commit(TARGET, "codex-pc", fence=1)


def test_fence_increases_and_stale_writer_is_blocked(tmp_path):
    store = LeaseStore(tmp_path)
    store.acquire(TARGET, "claude")
    store.release(TARGET, "claude")
    assert store.writer_count(TARGET) == 0
    assert store.acquire(TARGET, "codex-pc").fence == 2
    with pytest.raises(CollisionError):
        store.guard_commit(TARGET, "claude", fence=1)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
