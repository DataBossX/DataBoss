"""Smoke tests for the two absorbed plugins (safety_kernel, qa_auditor).

These run against the REAL installed plugins at the repo root ``/plugins`` —
they are the acceptance proof that the legacy safety kernel and QA auditor are
wrapped and callable through the Foundry plugin loader.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from databossx.plugins.loader import call_entrypoint, discover_plugins, validate_plugin

pydantic = pytest.importorskip("pydantic", reason="qa_auditor wraps pydantic models")


def test_both_absorbed_plugins_validate(real_plugins_dir: Path):
    names = {p.name: p for p in discover_plugins(real_plugins_dir)}
    assert "safety_kernel" in names and "qa_auditor" in names
    for name in ("safety_kernel", "qa_auditor"):
        loaded = validate_plugin(real_plugins_dir / name)
        assert loaded.valid, loaded.errors
        assert loaded.manifest.entrypoints  # declared, ast-verified


def test_safety_kernel_smoke(real_plugins_dir: Path, tmp_path: Path):
    result = call_entrypoint(
        real_plugins_dir, "safety_kernel:smoke", {"dir": str(tmp_path)}
    )
    assert result["ok"] is True
    v1, v2 = (Path(p) for p in result["writes"])
    assert v1.name == "smoke_v001.txt" and v1.read_text() == "first"
    assert v2.name == "smoke_v002.txt" and v2.read_text() == "second"
    assert result["latest"] == str(v2)
    audit_lines = Path(result["audit_log"]).read_text().splitlines()
    assert len(audit_lines) == 2
    assert all("versioned_write" in line for line in audit_lines)


def test_safety_kernel_versioned_write_never_overwrites(real_plugins_dir, tmp_path):
    payload = {"folder": str(tmp_path), "stem": "doc", "ext": ".txt", "data": "one"}
    first = call_entrypoint(real_plugins_dir, "safety_kernel:versioned_write", payload)
    second = call_entrypoint(
        real_plugins_dir, "safety_kernel:versioned_write", dict(payload, data="two")
    )
    assert (first["version"], second["version"]) == (1, 2)
    assert Path(first["path"]).read_text() == "one"


def test_safety_kernel_audit_appends(real_plugins_dir, tmp_path):
    log = tmp_path / "audit.log"
    for i in range(2):
        out = call_entrypoint(real_plugins_dir, "safety_kernel:audit", {
            "audit_log": str(log), "action": "unit_test", "detail": f"event {i}",
            "level": "WARN",
        })
        assert "unit_test" in out["line"]
    lines = log.read_text().splitlines()
    assert len(lines) == 2 and all("WARN" in line for line in lines)


def test_qa_auditor_smoke(real_plugins_dir):
    result = call_entrypoint(real_plugins_dir, "qa_auditor:smoke", {})
    assert result["ok"] is True
    assert result["clean_case"]["passed"] is True
    assert result["dirty_case"]["passed"] is False
    assert result["dirty_case"]["first_issue"]["severity"] == "error"


def test_qa_auditor_audit_report_flags_over_conveyance(real_plugins_dir):
    result = call_entrypoint(real_plugins_dir, "qa_auditor:audit_report", {
        "rows": [{
            "grantor": "A", "grantee": "B", "instrument_number": "2024-9",
            "legal_description": "SW/4",
            "conveyed_interest": "3/4", "retained_interest": "1/2",
        }],
    })
    assert result["passed"] is False
    assert any("8/8" in i["message"] for i in result["issues"])


def test_qa_auditor_missing_rows_is_an_error(real_plugins_dir):
    from databossx.errors import PluginError

    with pytest.raises(PluginError, match="rows"):
        call_entrypoint(real_plugins_dir, "qa_auditor:audit_report", {})


def test_absorbed_manifests_are_honest(real_plugins_dir):
    kernel = json.loads((real_plugins_dir / "safety_kernel" / "plugin.json").read_text())
    qa = json.loads((real_plugins_dir / "qa_auditor" / "plugin.json").read_text())
    assert "filesystem:write" in kernel["permissions"]
    # qa_auditor only reads (golden source); it must not claim write access.
    assert qa["permissions"] == ["filesystem:read"]
    assert any(r.startswith("pydantic") for r in qa["requires"]["python"])
