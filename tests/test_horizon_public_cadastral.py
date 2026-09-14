"""Allowlisted public cadastral plat binding."""

from pathlib import Path

import pytest

from horizon.public_cadastral import (
    PublicCadastralError,
    bind_local_plat,
    build_receipt,
    hash_local_plat,
    main,
    plat_url,
)


def _tiny_pdf(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.1\n1 0 obj<<>>endobj\ntrailer<<>>\n")
    return path


def test_unknown_township_is_rejected() -> None:
    with pytest.raises(PublicCadastralError, match="allowlist"):
        plat_url("campbell", "40n", "70w")


def test_local_allowlisted_plat_is_hashed(tmp_path: Path) -> None:
    pdf = _tiny_pdf(tmp_path / "t45nr76w.pdf")
    digest, size = hash_local_plat(pdf)
    binding = bind_local_plat("campbell", "45n", "76w", pdf)
    assert binding.sha256 == digest
    assert binding.size_bytes == size
    assert binding.url.endswith("/campbell/t45nr76w.pdf")
    receipt = build_receipt([binding])
    assert receipt.technical_pass
    assert "not a section abstract package" in receipt.notes[0]


def test_cli_binds_local_plat(tmp_path: Path) -> None:
    pdf = _tiny_pdf(tmp_path / "plat.pdf")
    output = tmp_path / "receipt.json"
    result = main(
        [
            "--output",
            str(output),
            "--plat",
            f"johnson,47n,77w,{pdf}",
        ]
    )
    assert result == 0
    payload = output.read_text(encoding="utf-8")
    assert "johnson" in payload
    assert "dbx.public_cadastral_receipt" in payload
