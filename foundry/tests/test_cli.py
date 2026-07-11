"""End-to-end CLI tests: the DEFINITION-OF-DONE flow through cli.main()."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from databossx.cli import main


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "databossx" in capsys.readouterr().out


def test_new_then_run_then_discover(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.setenv("DATABOSSX_ROOT", str(tmp_path))

    assert main(["new", "demo"]) == 0
    out = capsys.readouterr().out
    assert "created: PLAN.md" in out

    assert main(["run", "demo.hello"]) == 0
    out = capsys.readouterr().out
    assert "hello from demo" in out
    assert "demo.hello: success" in out
    result = tmp_path / "projects" / "demo" / "outputs" / "hello_result_v001.json"
    assert result.is_file()

    # Point discovery at a fabricated work root.
    horizon = tmp_path / "Horizon"
    (horizon / "county_a").mkdir(parents=True)
    (horizon / "county_a" / "deed.pdf").write_text("%PDF")
    monkeypatch.setenv("DATABOSSX_DISCOVER_ROOTS", str(horizon))
    assert main(["discover"]) == 0
    out = capsys.readouterr().out
    assert "county_a" in out and "no_ocr" in out
    registry = json.loads((tmp_path / "registry.json").read_text())
    assert registry["projects"][0]["name"] == "county_a"


def test_new_rejects_bad_name(tmp_path: Path, capsys, monkeypatch):
    monkeypatch.setenv("DATABOSSX_ROOT", str(tmp_path))
    assert main(["new", "Bad.Name"]) == 1
    assert "invalid project name" in capsys.readouterr().err


def test_run_failure_exit_code(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("DATABOSSX_ROOT", str(tmp_path))
    main(["new", "demo"])
    plan = tmp_path / "projects" / "demo" / "PLAN.md"
    plan.write_text('## Tasks\n\n### boom\n- cmd: {python} -c "raise SystemExit(2)"\n')
    capsys.readouterr()
    assert main(["run", "demo.boom"]) == 1
    assert "failed" in capsys.readouterr().err


def test_doctor_writes_report_and_exit_code(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("DATABOSSX_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    code = main(["doctor", "--core-only"])
    out = capsys.readouterr().out
    report = json.loads((tmp_path / "doctor_report.json").read_text())
    # python/pip/git all exist wherever this suite runs.
    assert code == 0 and report["clean"] is True
    assert "result: CLEAN" in out


def test_doctor_out_override_and_unclean(tmp_path: Path, monkeypatch, capsys):
    import databossx.doctor as doc

    monkeypatch.setenv("DATABOSSX_ROOT", str(tmp_path))
    monkeypatch.setattr(doc, "run_doctor",
                        lambda **kw: doc.DoctorResult(reports=[
                            doc.ToolReport(key="git", label="Git", found=False,
                                           required=True, install_hint="apt install git"),
                        ], platform="linux"))
    code = main(["doctor", "--out", str(tmp_path / "sub" / "r.json")])
    assert code == 2
    assert (tmp_path / "sub" / "r.json").is_file()
    assert "error:" in capsys.readouterr().err


def test_env_cli(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("DATABOSSX_ROOT", str(tmp_path))
    main(["new", "demo"])
    capsys.readouterr()
    assert main(["env", "demo"]) == 0
    out = capsys.readouterr().out
    assert "env demo: created" in out
    assert (tmp_path / "projects" / "demo" / "requirements.lock").is_file()


def test_plugins_list_validate_run_cli(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("DATABOSSX_ROOT", str(tmp_path))
    plugin = tmp_path / "plugins" / "toy"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text(json.dumps({
        "name": "toy", "version": "0.1.0", "description": "toy plugin",
        "entrypoints": {"echo": "entry:echo"}, "permissions": [],
        "requires": {"tools": [], "python": []},
    }))
    (plugin / "entry.py").write_text("def echo(payload):\n    return payload\n")

    assert main(["plugins", "list"]) == 0
    assert "toy 0.1.0" in capsys.readouterr().out

    assert main(["plugins", "validate", "toy"]) == 0
    assert "ok: toy" in capsys.readouterr().out

    assert main(["plugins", "run", "toy:echo", "--json", '{"a": 1}']) == 0
    assert json.loads(capsys.readouterr().out) == {"a": 1}

    assert main(["plugins", "run", "toy:echo", "--json", "[1]"]) == 1
    assert "JSON object" in capsys.readouterr().err


def test_plugins_validate_reports_invalid(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("DATABOSSX_ROOT", str(tmp_path))
    plugin = tmp_path / "plugins" / "broken"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text("{}")
    assert main(["plugins", "validate"]) == 1
    out = capsys.readouterr().out
    assert "INVALID: broken" in out


def test_plugins_list_empty(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("DATABOSSX_ROOT", str(tmp_path))
    assert main(["plugins", "list"]) == 0
    assert "no plugins installed" in capsys.readouterr().out
