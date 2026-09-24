"""Tests for the STAGED_EVIDENCE lane and deterministic package gates."""

import zipfile

from horizon.package_gate import build_zip, readback_matches, record_cycle, verify_zip
from horizon.staging import patch_manifest, record_fingerprint, validate


def _rec(key="0001-0001", **kw):
    base = {
        "section": "12-45N-76W",
        "stable_key": key,
        "source_drive_id": "drive-id",
        "source_sha256": "a" * 64,
        "disposition": "INCLUDE",
        "confidence": "PIXEL_READ",
        "evidence": [{"physical_page": 1, "visible_anchor": "WARRANTY DEED"}],
        "doc_type": "Warranty Deed",
        "grantor": ["A"],
        "grantee": ["B"],
    }
    base.update(kw)
    return base


def test_fingerprint_is_key_order_independent():
    assert record_fingerprint({"a": 1, "b": 2}) == record_fingerprint({"b": 2, "a": 1})


def test_exact_duplicates_collapse():
    res = validate([_rec(), _rec()], "12-45N-76W")
    assert res.duplicates == 1 and len(res.accepted) == 1 and not res.issues


def test_section_contamination_rejected():
    res = validate([_rec(section="14-45N-76W")], "12-45N-76W")
    assert not res.accepted and res.by_code("SECTION_CONTAMINATION")


def test_collision_and_missing_evidence_block_patch():
    recs = [_rec(), _rec(grantee=["C"]), _rec("0002-0002", evidence=[], confidence="OCR_LOCATOR_ONLY")]
    res = validate(recs, "12-45N-76W")
    assert res.by_code("STABLE_KEY_COLLISION")
    assert res.by_code("MISSING_EVIDENCE") and res.by_code("NOT_PIXEL_AUTHORITY")
    assert patch_manifest(res, {}) == []


def test_patch_manifest_reports_only_changes():
    res = validate([_rec(grantee=["B", "C"])], "12-45N-76W")
    patch = patch_manifest(res, {"0001-0001": {"doc_type": "Warranty Deed", "grantor": ["A"], "grantee": ["B"]}})
    assert len(patch) == 1 and set(patch[0]["changes"]) == {"grantee"}


def test_non_target_always_surfaces():
    res = validate([_rec(disposition="NON_TARGET")], "12-45N-76W")
    patch = patch_manifest(res, {"0001-0001": {"doc_type": "Warranty Deed", "grantor": ["A"], "grantee": ["B"]}})
    assert patch and patch[0]["disposition"] == "NON_TARGET"


def test_zip_is_deterministic_and_verified(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("alpha")
    b.write_text("beta")
    z1, z2 = tmp_path / "1.zip", tmp_path / "2.zip"
    assert build_zip(z1, [a, b]) == build_zip(z2, [a, b])
    rep = verify_zip(z1, ["a.txt", "b.txt"])
    assert rep.passed and set(rep.members) == {"a.txt", "b.txt"}
    assert not verify_zip(z1, ["a.txt"]).passed
    assert readback_matches(z1, z2)
    with zipfile.ZipFile(z1) as zf:
        assert zf.getinfo("a.txt").date_time == (1980, 1, 1, 0, 0, 0)


def test_clean_cycle_streak_resets_on_sha_change(tmp_path):
    ledger = tmp_path / "ledger.json"
    assert record_cycle(ledger, "s1", True) == 1
    assert record_cycle(ledger, "s1", True) == 2
    assert record_cycle(ledger, "s2", True) == 1
    assert record_cycle(ledger, "s2", False) == 0
    assert record_cycle(ledger, "s2", True) == 1
