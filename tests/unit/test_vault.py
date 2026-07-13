"""Tests for databossx.vault.store.Vault."""

from __future__ import annotations

import hashlib

import pytest

from databossx.vault.store import Vault


@pytest.fixture()
def vault(tmp_path):
    return Vault(tmp_path / "vault_root")


def test_put_and_get_roundtrip(vault):
    data = b"hello, evidence vault"
    digest = vault.put(data)
    assert digest == hashlib.sha256(data).hexdigest()
    assert vault.get(digest) == data


def test_has(vault):
    data = b"some bytes"
    assert not vault.has(hashlib.sha256(data).hexdigest())
    digest = vault.put(data)
    assert vault.has(digest)


def test_get_missing_raises_keyerror(vault):
    with pytest.raises(KeyError):
        vault.get("0" * 64)


def test_put_is_idempotent(vault):
    data = b"idempotent content"
    digest1 = vault.put(data)
    path1 = vault.path_for(digest1)
    mtime1 = path1.stat().st_mtime_ns

    digest2 = vault.put(data)
    path2 = vault.path_for(digest2)
    mtime2 = path2.stat().st_mtime_ns

    assert digest1 == digest2
    # Second put must not rewrite the existing file.
    assert mtime1 == mtime2


def test_path_for_uses_sha256_prefix_layout(vault):
    data = b"layout test"
    digest = vault.put(data)
    expected_path = vault.root / "sha256" / digest[:2] / digest
    assert vault.path_for(digest) == expected_path
    assert expected_path.is_file()


def test_put_file_copies_and_hashes_correctly(vault, tmp_path):
    src = tmp_path / "source.txt"
    content = b"file contents for hashing"
    src.write_bytes(content)

    digest = vault.put_file(src)
    assert digest == hashlib.sha256(content).hexdigest()
    assert vault.get(digest) == content


def test_put_file_does_not_modify_source(vault, tmp_path):
    src = tmp_path / "original.txt"
    content = b"do not touch me"
    src.write_bytes(content)
    original_mtime = src.stat().st_mtime_ns

    vault.put_file(src)

    assert src.is_file()
    assert src.read_bytes() == content
    assert src.stat().st_mtime_ns == original_mtime


def test_put_file_idempotent(vault, tmp_path):
    src = tmp_path / "dup.txt"
    content = b"duplicate content"
    src.write_bytes(content)

    digest1 = vault.put_file(src)
    digest2 = vault.put_file(src)
    assert digest1 == digest2


def test_verify_true_for_intact_content(vault):
    data = b"verify me"
    digest = vault.put(data)
    assert vault.verify(digest) is True


def test_verify_false_for_missing_content(vault):
    assert vault.verify("f" * 64) is False


def test_verify_false_for_corrupted_content(vault):
    data = b"will be corrupted"
    digest = vault.put(data)
    path = vault.path_for(digest)
    path.write_bytes(b"tampered bytes")
    assert vault.verify(digest) is False


def test_different_content_hashes_differently(vault):
    d1 = vault.put(b"content one")
    d2 = vault.put(b"content two")
    assert d1 != d2
    assert vault.get(d1) == b"content one"
    assert vault.get(d2) == b"content two"
