"""Tests for doto_image_commander/core/config.py."""
import importlib

import pytest

pytest.importorskip("dotenv")
core_config = importlib.import_module("core.config")
config = core_config.config


def test_cost_defaults_are_numeric():
    assert isinstance(config.OKCOUNTY_COST_PER_IMAGE, float)
    assert isinstance(config.OKCOUNTY_COST_PER_SEARCH, float)
    assert config.OKCOUNTY_COST_PER_IMAGE >= 0
    assert config.OKCOUNTY_COST_PER_SEARCH >= 0


def test_instrument_type_map_canonicalizes():
    m = config.INSTRUMENT_TYPE_MAP
    assert m["wd"] == "Warranty Deed"
    assert m["oil and gas lease"] == "Oil and Gas Lease"
    assert m["qcd"] == "Quit Claim Deed"


def test_ok_counties_complete():
    # Oklahoma has 77 counties.
    assert len(config.OK_COUNTIES) == 77
    assert "Oklahoma" in config.OK_COUNTIES
    assert "Tulsa" in config.OK_COUNTIES


def test_base_url_is_https():
    assert config.OKCOUNTY_API_BASE_URL.startswith("https://")
