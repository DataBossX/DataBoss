"""Tests for backend/logging_utils.py secret redaction (pure stdlib)."""
import importlib

lu = importlib.import_module("logging_utils")


def test_redacts_openai_key():
    out = lu.redact("token sk-ABCDEF1234567890 abc")
    assert "sk-ABCDEF1234567890" not in out
    assert "REDACTED" in out


def test_redacts_anthropic_key():
    out = lu.redact("key sk-ant-abc_DEF-123456 end")
    assert "sk-ant-abc_DEF-123456" not in out


def test_redacts_bearer_token():
    out = lu.redact("Authorization: Bearer abcdef0123456789xyz")
    assert "abcdef0123456789xyz" not in out


def test_redacts_explicit_extra_secret():
    secret = "supersecretvalue123"
    out = lu.redact(f"db password is {secret}", extra_secrets=[secret])
    assert secret not in out


def test_leaves_plain_text_untouched():
    msg = "DataBossX API started normally"
    assert lu.redact(msg) == msg


def test_handles_empty_and_none():
    assert lu.redact("") == ""
    assert lu.redact(None) is None  # type: ignore[arg-type]


def test_redaction_filter_masks_record():
    import logging
    f = lu.RedactionFilter(extra_secrets=["topsecret"])
    rec = logging.LogRecord(
        "n", logging.INFO, __file__, 1,
        "leak sk-ABCDEFGH12345678 and topsecret", (), None,
    )
    assert f.filter(rec) is True
    assert "sk-ABCDEFGH12345678" not in rec.getMessage()
    assert "topsecret" not in rec.getMessage()
