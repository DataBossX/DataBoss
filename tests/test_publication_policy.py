"""Tests for the public-repository publication gate."""

import json
from pathlib import Path

from scripts.check_publication_policy import (
    Finding,
    filter_hash_bound_baseline,
    load_config,
    main,
    scan_paths,
)


CONFIG_PATH = Path(__file__).parents[1] / "config" / "publication_policy.json"


def _config() -> dict[str, object]:
    return load_config(CONFIG_PATH)


def _write_config(path: Path, config: dict[str, object] | None = None) -> Path:
    if config is None:
        config = _config()
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_accepts_safe_text_file(tmp_path):
    (tmp_path / "safe.txt").write_text("Public content.\n", encoding="utf-8")

    assert scan_paths(tmp_path, ["safe.txt"], _config()) == []


def test_rejects_protected_project_path_without_reading_file(tmp_path):
    findings = scan_paths(
        tmp_path,
        ["projects/OK-BECKHAM-32-11N-25W/project_manifest.json"],
        _config(),
    )
    assert {finding.rule_id for finding in findings} == {"oklahoma_project_control"}


def test_rejects_private_content_and_redacts_match(tmp_path, capsys):
    source = tmp_path / "settings.py"
    private_link = (
        "https://drive." + "google.com/file/d/" + "abcdefghijklmnopqrstuvwxyz"
    )
    source.write_text(f'LINK = "{private_link}"\n', encoding="utf-8")

    config_path = _write_config(tmp_path / "policy.json")

    assert main(
        [
            "--root",
            str(tmp_path),
            "--config",
            str(config_path),
            "settings.py",
        ]
    ) == 1
    output = capsys.readouterr().out
    assert "drive_object_link" in output
    assert private_link not in output


def test_scans_decodable_content_inside_binary_file(tmp_path):
    (tmp_path / "data.bin").write_bytes(
        b"\xff-----BEGIN DSA " + b"PRIVATE KEY-----\x00"
    )

    findings = scan_paths(tmp_path, ["data.bin"], _config())

    assert [finding.rule_id for finding in findings] == ["private_key"]


def test_documentation_content_is_scanned(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "operator.md").write_text(
        "Example only: " + "D:\\Data" + "Boss\\private",
        encoding="utf-8",
    )

    findings = scan_paths(tmp_path, ["docs/operator.md"], _config())

    assert [finding.rule_id for finding in findings] == ["private_windows_path"]


def test_rejects_path_traversal():
    unsafe_paths = [
        "../outside.txt",
        "nested/../../outside.txt",
        "/absolute/path.txt",
        r"C:\absolute\path.txt",
    ]

    findings = scan_paths(Path("/tmp"), unsafe_paths, _config())

    assert [finding.rule_id for finding in findings] == [
        "path_traversal",
        "path_traversal",
        "path_traversal",
        "path_traversal",
    ]


def test_redacts_forbidden_paths_with_control_characters(tmp_path, capsys):
    config_path = _write_config(tmp_path / "policy.json")
    unsafe_path = "projects/OK-DEMO\nforged-output/file.txt"

    assert main(
        [
            "--root",
            str(tmp_path),
            "--config",
            str(config_path),
            unsafe_path,
        ]
    ) == 1
    output = capsys.readouterr().out
    assert "<redacted path>" in output
    assert unsafe_path not in output


def test_credential_rule_allows_only_exact_env_example_name(tmp_path):
    for safe_name in (".env.example", ".environment"):
        (tmp_path / safe_name).write_text("", encoding="utf-8")

    assert scan_paths(tmp_path, [".env.example", ".environment"], _config()) == []

    findings = scan_paths(tmp_path, [".env", ".env.local"], _config())
    assert [finding.rule_id for finding in findings] == [
        "credential_file",
        "credential_file",
    ]


def test_oversized_file_fails_closed(tmp_path, capsys):
    (tmp_path / "large.txt").write_text("four", encoding="utf-8")
    config = _config()
    config["max_text_file_bytes"] = 3
    config_path = _write_config(tmp_path / "policy.json", config)

    assert main(
        [
            "--root",
            str(tmp_path),
            "--config",
            str(config_path),
            "large.txt",
        ]
    ) == 2
    assert "exceeds the 3-byte scan limit" in capsys.readouterr().err


def test_symlink_fails_closed(tmp_path, capsys):
    target = tmp_path / "target.txt"
    target.write_text("Public content.\n", encoding="utf-8")
    (tmp_path / "link.txt").symlink_to(target)
    config_path = _write_config(tmp_path / "policy.json")

    assert main(
        [
            "--root",
            str(tmp_path),
            "--config",
            str(config_path),
            "link.txt",
        ]
    ) == 2
    assert "refusing to follow symbolic link" in capsys.readouterr().err


def test_invalid_regex_fails_closed(tmp_path, capsys):
    config = _config()
    config["forbidden_path_rules"] = [
        {"id": "broken", "message": "Broken rule.", "pattern": "["}
    ]
    config_path = _write_config(tmp_path / "invalid-regex.json", config)

    assert main(
        [
            "--root",
            str(tmp_path),
            "--config",
            str(config_path),
            "safe.txt",
        ]
    ) == 2
    assert "not a valid regular expression" in capsys.readouterr().err


def test_invalid_configuration_fails_closed(tmp_path, capsys):
    config_path = tmp_path / "invalid.json"
    config_path.write_text("{}", encoding="utf-8")

    assert main(
        [
            "--root",
            str(tmp_path),
            "--config",
            str(config_path),
            "safe.txt",
        ]
    ) == 2
    assert "failed safely" in capsys.readouterr().err


def test_hash_bound_baseline_suppresses_only_exact_legacy_file(tmp_path):
    legacy = tmp_path / "legacy.md"
    legacy.write_text("known legacy content", encoding="utf-8")
    config = {
        "hash_bound_baseline": [
            {
                "path": "legacy.md",
                "sha256": (
                    "1c3114fb7cba094feb7101ff2771dd00c6aa296630a2fc4bf6"
                    "37257830cf4051"
                ),
                "rule_ids": ["legacy_rule"],
            }
        ]
    }
    finding = Finding("legacy.md", "legacy_rule", "Known legacy finding.")

    assert filter_hash_bound_baseline(tmp_path, [finding], config) == []

    legacy.write_text("changed legacy content", encoding="utf-8")
    assert filter_hash_bound_baseline(tmp_path, [finding], config) == [finding]


def test_hash_bound_baseline_does_not_hide_new_rule(tmp_path):
    legacy = tmp_path / "legacy.md"
    legacy.write_text("known legacy content", encoding="utf-8")
    config = {
        "hash_bound_baseline": [
            {
                "path": "legacy.md",
                "sha256": (
                    "1c3114fb7cba094feb7101ff2771dd00c6aa296630a2fc4bf6"
                    "37257830cf4051"
                ),
                "rule_ids": ["legacy_rule"],
            }
        ]
    }
    findings = [
        Finding("legacy.md", "legacy_rule", "Known legacy finding."),
        Finding("legacy.md", "new_rule", "New finding."),
    ]

    assert filter_hash_bound_baseline(tmp_path, findings, config) == findings
