"""Tests for curative recommendations on defects."""

import pytest

from databossx.curative import enrich_defects, recommend


def test_recommend_by_category():
    assert "8/8" in recommend("ownership-8/8")
    assert "OCR" in recommend("missing-evidence")
    assert "runsheet" in recommend("chain-break").lower()


def test_over_conveyance_gets_specific_action():
    rec = recommend("examiner-review",
                    "Grantor conveyed 1/2 but only held 1/4 (over-conveyance).")
    assert "over-conveyance" in rec.lower()
    assert "actual interest" in rec.lower()


def test_chain_of_title_break_specific_action():
    rec = recommend("examiner-review",
                    "Grantor X does not match prior grantee Y (chain-of-title break)")
    assert "intervening conveyance" in rec.lower()


def test_unknown_category_falls_back():
    assert recommend("something-new") == recommend("", "")


def test_enrich_defects_is_idempotent_and_in_place():
    defects = [{"category": "chain-break", "detail": ""},
               {"category": "ownership-8/8", "detail": "", "curative": "KEEP"}]
    enrich_defects(defects)
    assert defects[0]["curative"]  # filled
    assert defects[1]["curative"] == "KEEP"  # not overwritten
    # Running again changes nothing.
    first = defects[0]["curative"]
    enrich_defects(defects)
    assert defects[0]["curative"] == first


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
