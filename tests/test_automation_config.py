"""Tests for automation/config.py (stdlib tomllib)."""
import importlib

cfg = importlib.import_module("automation.config")
AutomationConfig = cfg.AutomationConfig
load_config = cfg.load_config


def test_defaults_when_missing(tmp_path):
    c = load_config(tmp_path / "nope.toml")
    assert c.base_url.startswith("https://")
    assert c.sheet_dsu == "DSU NOTICE LIST"
    assert c.retries == 3


def test_loads_real_repo_settings():
    # The repo ships config/settings.toml; loader should read it.
    c = load_config()
    assert "weldgov.com" in c.base_url
    assert c.extractor_model.startswith("anthropic:")
    assert c.reasoner_model.startswith("openai:")


def test_partial_file_uses_fallbacks(tmp_path):
    p = tmp_path / "settings.toml"
    p.write_text('[site]\nbase_url = "https://example.test/"\n')
    c = load_config(p)
    assert c.base_url == "https://example.test/"
    # Missing sections fall back to defaults.
    assert c.sheet_offset == "OFFSET NOTICE LIST"
    assert c.max_concurrent == 6


def test_malformed_file_falls_back(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text("this is = = not valid toml [[[")
    c = load_config(p)
    assert c == AutomationConfig()


def test_from_dict_types():
    c = AutomationConfig.from_dict({
        "site": {"base_url": "https://x/", "delay_sec": 2},
        "execution": {"retries": 5, "timeout_sec": 99},
    })
    assert c.delay_sec == 2.0 and isinstance(c.delay_sec, float)
    assert c.retries == 5
    assert c.timeout_sec == 99
