from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from databossx import doctor


def fake_run_factory(version_text="tool 9.9.9", returncode=0, to_stderr=False):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        out = "" if to_stderr else version_text
        err = version_text if to_stderr else ""
        return subprocess.CompletedProcess(argv, returncode, stdout=out, stderr=err)

    fake_run.calls = calls
    return fake_run


def test_check_tool_found_with_version():
    spec = doctor.TOOLS[0]  # python
    report = doctor.check_tool(
        spec, "linux",
        which=lambda name: f"/usr/bin/{name}",
        run=fake_run_factory("Python 3.11.15"),
    )
    assert report.found and report.version == "3.11.15"
    assert report.path == "/usr/bin/python"


def test_check_tool_reads_stderr_versions():
    java = next(t for t in doctor.TOOLS if t.key == "java")
    report = doctor.check_tool(
        java, "linux",
        which=lambda name: "/usr/bin/java",
        run=fake_run_factory('openjdk version "17.0.9" 2023-10-17', to_stderr=True),
    )
    assert report.found and report.version.startswith("17.0")


def test_version_prefers_number_after_the_word_version():
    java = next(t for t in doctor.TOOLS if t.key == "java")
    noisy = (
        "Picked up JAVA_TOOL_OPTIONS: -Dhttps.proxyHost=127.0.0.1 "
        "-Dhttps.proxyPort=44407\n"
        'openjdk version "21.0.10" 2026-01-20\n'
    )
    report = doctor.check_tool(
        java, "linux",
        which=lambda name: "/usr/bin/java",
        run=fake_run_factory(noisy, to_stderr=True),
    )
    assert report.version == "21.0.10"


def test_check_tool_missing_carries_install_hint():
    tess = next(t for t in doctor.TOOLS if t.key == "tesseract")
    for platform_key, fragment in (
        ("windows", "winget"), ("linux", "apt-get"), ("darwin", "brew"),
    ):
        report = doctor.check_tool(tess, platform_key, which=lambda n: None,
                                   run=fake_run_factory())
        assert not report.found
        assert fragment in report.install_hint


def test_pip_fallback_via_python_module():
    pip = next(t for t in doctor.TOOLS if t.key == "pip")
    report = doctor.check_tool(
        pip, "linux",
        which=lambda name: None,
        run=fake_run_factory("pip 24.0 from ..."),
    )
    assert report.found
    assert report.path == f"{sys.executable} -m pip"


def test_version_probe_survives_crashing_tool():
    def exploding_run(argv, **kwargs):
        raise OSError("boom")

    spec = doctor.TOOLS[0]
    report = doctor.check_tool(spec, "linux", which=lambda n: "/usr/bin/python",
                               run=exploding_run)
    assert report.found and report.version is None


def test_run_doctor_clean_and_report_written(tmp_path: Path):
    result = doctor.run_doctor(
        which=lambda name: f"/usr/bin/{name}",
        run=fake_run_factory("9.9.9"),
        platform_key="linux",
    )
    assert result.clean
    assert len(result.reports) == len(doctor.TOOLS)
    out = doctor.write_report(result, tmp_path / "doctor_report.json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["clean"] is True
    assert {t["key"] for t in data["tools"]} == {t.key for t in doctor.TOOLS}


def test_run_doctor_unclean_when_tool_missing():
    result = doctor.run_doctor(
        which=lambda name: None if name == "tesseract" else f"/usr/bin/{name}",
        run=fake_run_factory(),
        platform_key="linux",
    )
    assert not result.clean
    assert [r.key for r in result.missing_required] == ["tesseract"]
    text = doctor.format_report(result)
    assert "NOT CLEAN" in text and "tesseract" in text


def test_core_only_restricts_tool_set():
    result = doctor.run_doctor(
        which=lambda name: None, run=fake_run_factory(returncode=1),
        platform_key="linux", core_only=True,
    )
    assert {r.key for r in result.reports} == set(doctor.CORE_TOOLS)


def test_install_missing_runs_platform_commands():
    result = doctor.run_doctor(
        which=lambda name: None if name in ("tesseract", "gs", "gswin64c", "gswin32c")
        else f"/usr/bin/{name}",
        run=fake_run_factory(),
        platform_key="linux",
    )
    ran = []

    def record_run(cmd, **kwargs):
        ran.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    attempts = doctor.install_missing(result, run=record_run)
    assert [a[0] for a in attempts] == ["tesseract", "ghostscript"]
    assert all(rc == 0 for _, _, rc in attempts)
    assert any("tesseract-ocr" in cmd for cmd in ran)


def test_install_missing_handles_failures():
    result = doctor.run_doctor(
        which=lambda name: None if name == "docker" else f"/usr/bin/{name}",
        run=fake_run_factory(), platform_key="linux",
    )

    def failing_run(cmd, **kwargs):
        raise OSError("no package manager")

    attempts = doctor.install_missing(result, run=failing_run)
    assert attempts == [("docker", "sudo apt-get install -y docker.io", 1)]


def test_current_platform_returns_known_key():
    assert doctor.current_platform() in ("windows", "linux", "darwin")
