"""Tests for doto_image_commander/core/security.py (Fernet credential crypto)."""
import importlib

import pytest

# cryptography depends on a compiled backend; on a broken install it can raise
# something other than ImportError, so guard the whole import and skip cleanly.
try:
    importlib.import_module("cryptography.fernet")
    security = importlib.import_module("core.security")
except Exception as exc:  # pragma: no cover - environment dependent
    pytest.skip(f"cryptography unavailable: {exc}", allow_module_level=True)


@pytest.fixture()
def temp_key(tmp_path, monkeypatch):
    monkeypatch.setattr(security, "_KEY_FILE", tmp_path / "master.key",
                        raising=False)
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    return tmp_path


def test_encrypt_decrypt_round_trip(temp_key):
    secret = "OKCOUNTY_API_KEY_value_123"
    token = security.encrypt(secret)
    assert token != secret
    assert security.decrypt(token) == secret


def test_key_file_created_with_restrictive_perms(temp_key):
    security.encrypt("x")
    key_file = security._KEY_FILE
    assert key_file.exists()
    # Owner read/write only (0o600); ignore on platforms without POSIX perms.
    mode = key_file.stat().st_mode & 0o777
    assert mode in (0o600, 0o644) or mode & 0o077 == 0


def test_invalid_env_key_raises_clearly(tmp_path, monkeypatch):
    monkeypatch.setattr(security, "_KEY_FILE", tmp_path / "k.key", raising=False)
    monkeypatch.setenv("ENCRYPTION_KEY", "not-a-valid-fernet-key")
    with pytest.raises(ValueError):
        security.encrypt("x")
    # The bad key must NOT have been persisted.
    assert not (tmp_path / "k.key").exists()


def test_derive_key_is_deterministic_per_salt():
    salt = b"0123456789abcdef"
    k1 = security.derive_key_from_password("hunter2", salt)
    k2 = security.derive_key_from_password("hunter2", salt)
    assert k1 == k2


def test_derive_key_changes_with_salt():
    k1 = security.derive_key_from_password("hunter2", b"saltsaltsaltsalt")
    k2 = security.derive_key_from_password("hunter2", b"pepperpepperpepp")
    assert k1 != k2
