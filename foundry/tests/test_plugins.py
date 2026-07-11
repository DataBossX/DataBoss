from __future__ import annotations

import json
from pathlib import Path

import pytest

from databossx.errors import PluginError
from databossx.plugins.loader import (
    call_entrypoint,
    discover_plugins,
    validate_plugin,
)
from databossx.plugins.manifest import parse_manifest

GOOD_MANIFEST = {
    "name": "sample",
    "version": "1.0.0",
    "description": "sample plugin",
    "entrypoints": {"greet": "entry:greet"},
    "permissions": ["filesystem:read"],
    "requires": {"tools": [], "python": []},
}

ENTRY_SOURCE = '''\
CALLED_AT_IMPORT = []

def greet(payload):
    return {"ok": True, "who": payload.get("who", "world")}

def _private_helper():
    return 1
'''


def install_plugin(plugins_dir: Path, manifest: dict, entry_source: str = ENTRY_SOURCE,
                   name: str = None) -> Path:
    name = name or manifest.get("name", "sample")
    d = plugins_dir / name
    d.mkdir(parents=True)
    (d / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    (d / "entry.py").write_text(entry_source, encoding="utf-8")
    return d


# ---------------------------------------------------------------- manifest


def test_valid_manifest_parses():
    manifest, errors = parse_manifest(GOOD_MANIFEST)
    assert errors == []
    assert manifest.name == "sample"
    assert manifest.entrypoints == {"greet": "entry:greet"}
    assert manifest.permissions == ("filesystem:read",)


def test_manifest_collects_all_errors():
    bad = {
        "name": "Bad Name!",
        "version": "1.0",
        "entrypoints": {},
        "permissions": ["root_access"],
        "requires": {"tools": "tesseract"},
        "surprise": True,
    }
    manifest, errors = parse_manifest(bad)
    assert manifest is None
    text = "\n".join(errors)
    for fragment in ("'name'", "'version'", "'description'", "entrypoints",
                     "unknown permission", "requires.tools", "unknown top-level key"):
        assert fragment in text, f"missing error about {fragment}"


def test_manifest_rejects_non_object():
    manifest, errors = parse_manifest(["not", "a", "dict"])
    assert manifest is None and "JSON object" in errors[0]


@pytest.mark.parametrize("target", ["entry", "entry:", ":greet", "entry:1bad", "en try:x"])
def test_bad_entrypoint_targets(target):
    data = dict(GOOD_MANIFEST, entrypoints={"greet": target})
    manifest, errors = parse_manifest(data)
    assert manifest is None
    assert any("module:function" in e for e in errors)


# ---------------------------------------------------------------- loader


def test_validate_ok_plugin(tmp_path: Path):
    d = install_plugin(tmp_path, GOOD_MANIFEST)
    loaded = validate_plugin(d)
    assert loaded.valid, loaded.errors


def test_validation_never_executes_plugin_code(tmp_path: Path):
    bomb = "raise RuntimeError('imported!')\n\ndef greet(payload):\n    return {}\n"
    d = install_plugin(tmp_path, GOOD_MANIFEST, entry_source=bomb)
    loaded = validate_plugin(d)  # must not raise RuntimeError
    assert loaded.valid


def test_validate_flags_missing_module_and_function(tmp_path: Path):
    manifest = dict(GOOD_MANIFEST, entrypoints={
        "gone": "missing_module:f", "nofunc": "entry:not_there",
    })
    d = install_plugin(tmp_path, manifest)
    loaded = validate_plugin(d)
    assert not loaded.valid
    text = "\n".join(loaded.errors)
    assert "module file not found" in text
    assert "not defined at the top level" in text


def test_validate_flags_syntax_error_without_executing(tmp_path: Path):
    d = install_plugin(tmp_path, GOOD_MANIFEST, entry_source="def broken(:\n")
    loaded = validate_plugin(d)
    assert not loaded.valid
    assert any("syntax error" in e for e in loaded.errors)


def test_validate_flags_name_dir_mismatch(tmp_path: Path):
    d = install_plugin(tmp_path, GOOD_MANIFEST, name="wrong_dir")
    loaded = validate_plugin(d)
    assert any("does not match" in e for e in loaded.errors)


def test_validate_missing_manifest(tmp_path: Path):
    d = tmp_path / "empty"
    d.mkdir()
    loaded = validate_plugin(d)
    assert not loaded.valid and "missing manifest" in loaded.errors[0]


def test_validate_bad_json(tmp_path: Path):
    d = tmp_path / "sample"
    d.mkdir()
    (d / "plugin.json").write_text("{oops")
    loaded = validate_plugin(d)
    assert any("invalid JSON" in e for e in loaded.errors)


def test_discover_plugins_lists_only_manifest_dirs(tmp_path: Path):
    install_plugin(tmp_path, GOOD_MANIFEST)
    (tmp_path / "not_a_plugin").mkdir()
    (tmp_path / "loose_file.txt").write_text("x")
    plugins = discover_plugins(tmp_path)
    assert [p.name for p in plugins] == ["sample"]
    assert discover_plugins(tmp_path / "nonexistent") == []


# ---------------------------------------------------------------- execution


def test_call_entrypoint_runs_function(tmp_path: Path):
    install_plugin(tmp_path, GOOD_MANIFEST)
    result = call_entrypoint(tmp_path, "sample:greet", {"who": "foundry"})
    assert result == {"ok": True, "who": "foundry"}


def test_call_entrypoint_default_payload(tmp_path: Path):
    install_plugin(tmp_path, GOOD_MANIFEST)
    assert call_entrypoint(tmp_path, "sample:greet")["who"] == "world"


def test_call_entrypoint_errors(tmp_path: Path):
    install_plugin(tmp_path, GOOD_MANIFEST)
    with pytest.raises(PluginError, match="must be '<plugin>:<entrypoint>'"):
        call_entrypoint(tmp_path, "sample.greet")
    with pytest.raises(PluginError, match="not found"):
        call_entrypoint(tmp_path, "ghost:greet")
    with pytest.raises(PluginError, match="no entrypoint"):
        call_entrypoint(tmp_path, "sample:ghost")


def test_call_entrypoint_wraps_plugin_exceptions(tmp_path: Path):
    source = "def greet(payload):\n    raise ValueError('inner boom')\n"
    install_plugin(tmp_path, GOOD_MANIFEST, entry_source=source)
    with pytest.raises(PluginError, match="inner boom"):
        call_entrypoint(tmp_path, "sample:greet")


def test_invalid_plugin_refuses_to_run(tmp_path: Path):
    manifest = dict(GOOD_MANIFEST, version="not-semver")
    install_plugin(tmp_path, manifest)
    with pytest.raises(PluginError, match="failed validation"):
        call_entrypoint(tmp_path, "sample:greet")
