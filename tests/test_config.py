"""Tests for backend/config.py (pure stdlib — always runnable)."""
import importlib

config = importlib.import_module("config")
Settings = config.Settings


def _clear_env(monkeypatch):
    for key in [
        "SQLITE_DB_PATH", "CORS_ALLOW_ORIGINS", "MAX_UPLOAD_MB",
        "ALLOWED_UPLOAD_EXTENSIONS", "RATE_LIMIT_MAX", "RATE_LIMIT_WINDOW_SEC",
        "LOG_PATH", "LOG_LEVEL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_defaults_are_safe(monkeypatch):
    _clear_env(monkeypatch)
    s = Settings.from_env()
    assert s.cors_origins == ["http://localhost:3000"]
    assert s.allow_credentials is True
    assert s.max_upload_bytes == 25 * 1024 * 1024
    assert s.rate_limit_max == 60
    assert ".pdf" in s.allowed_upload_extensions


def test_wildcard_cors_disables_credentials(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")
    s = Settings.from_env()
    assert s.cors_origins == ["*"]
    assert s.allow_credentials is False


def test_csv_origins_parsed(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://a.com, https://b.com")
    s = Settings.from_env()
    assert s.cors_origins == ["https://a.com", "https://b.com"]


def test_custom_extensions_normalized(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("ALLOWED_UPLOAD_EXTENSIONS", "PDF, .Png, jpg")
    s = Settings.from_env()
    assert s.allowed_upload_extensions == {".pdf", ".png", ".jpg"}


def test_max_upload_mb_fractional(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("MAX_UPLOAD_MB", "0.5")
    s = Settings.from_env()
    assert s.max_upload_bytes == 512 * 1024


def test_invalid_numbers_fall_back_to_defaults(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("MAX_UPLOAD_MB", "not-a-number")
    monkeypatch.setenv("RATE_LIMIT_MAX", "abc")
    s = Settings.from_env()
    assert s.max_upload_bytes == 25 * 1024 * 1024
    assert s.rate_limit_max == 60


def test_validate_warns_without_keys(monkeypatch):
    _clear_env(monkeypatch)
    s = Settings.from_env()
    warnings = s.validate()
    assert any("LLM API keys" in w for w in warnings)
    assert s.configured_providers() == []


def test_configured_providers(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GEMINI_API_KEY", "g-test")
    s = Settings.from_env()
    assert set(s.configured_providers()) == {"openai", "gemini"}
