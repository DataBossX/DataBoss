"""``databossx doctor`` — environment diagnostics.

Detects every tool the DataBossX platform (core + known plugin domains) needs,
reports versions, prints exact install commands for anything missing, writes a
``doctor_report.json``, and exits nonzero until the environment is clean.

All lookups are injectable (``which``/``run``/``platform``) so the module is
fully testable without touching the host machine.
"""

from __future__ import annotations

import json
import logging
import platform as _platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .logs import utc_now_iso

log = logging.getLogger("databossx.doctor")

_VERSION_PATTERN = re.compile(r"(\d+\.\d+(?:\.\d+)?[\w.\-]*)")
# Prefer the number that follows the word "version" — tool banners (and env
# noise like proxy settings) can contain unrelated dotted numbers first.
_LABELED_VERSION_PATTERN = re.compile(
    r"version\s+\"?(\d+\.\d+(?:\.\d+)?[\w.\-]*)\"?", re.IGNORECASE
)


@dataclass(frozen=True)
class ToolSpec:
    """How to detect one tool and how to install it per platform."""

    key: str
    label: str
    commands: Tuple[str, ...]
    version_args: Tuple[str, ...] = ("--version",)
    required: bool = True
    # Fallback: treat the tool as present when `sys.executable -m <module>` works.
    fallback_module: Optional[str] = None
    install: Dict[str, str] = field(default_factory=dict)


TOOLS: Tuple[ToolSpec, ...] = (
    ToolSpec(
        key="python", label="Python", commands=("python", "python3", "py"),
        install={
            "windows": "winget install -e --id Python.Python.3.12",
            "linux": "sudo apt-get install -y python3 python3-venv",
            "darwin": "brew install python@3.12",
        },
    ),
    ToolSpec(
        key="pip", label="pip", commands=("pip", "pip3"), fallback_module="pip",
        install={
            "windows": "python -m ensurepip --upgrade",
            "linux": "sudo apt-get install -y python3-pip",
            "darwin": "python3 -m ensurepip --upgrade",
        },
    ),
    ToolSpec(
        key="uv", label="uv", commands=("uv",),
        install={
            "windows": "winget install -e --id astral-sh.uv",
            "linux": 'curl -LsSf https://astral.sh/uv/install.sh | sh',
            "darwin": "brew install uv",
        },
    ),
    ToolSpec(
        key="node", label="Node.js", commands=("node",),
        install={
            "windows": "winget install -e --id OpenJS.NodeJS.LTS",
            "linux": "sudo apt-get install -y nodejs",
            "darwin": "brew install node",
        },
    ),
    ToolSpec(
        key="npm", label="npm", commands=("npm",),
        install={
            "windows": "winget install -e --id OpenJS.NodeJS.LTS",
            "linux": "sudo apt-get install -y npm",
            "darwin": "brew install node",
        },
    ),
    ToolSpec(
        key="git", label="Git", commands=("git",),
        install={
            "windows": "winget install -e --id Git.Git",
            "linux": "sudo apt-get install -y git",
            "darwin": "brew install git",
        },
    ),
    ToolSpec(
        key="docker", label="Docker", commands=("docker",),
        install={
            "windows": "winget install -e --id Docker.DockerDesktop",
            "linux": "sudo apt-get install -y docker.io",
            "darwin": "brew install --cask docker",
        },
    ),
    ToolSpec(
        key="tesseract", label="Tesseract OCR", commands=("tesseract",),
        install={
            "windows": "winget install -e --id UB-Mannheim.TesseractOCR",
            "linux": "sudo apt-get install -y tesseract-ocr",
            "darwin": "brew install tesseract",
        },
    ),
    ToolSpec(
        key="poppler", label="Poppler (pdftoppm)", commands=("pdftoppm",), version_args=("-v",),
        install={
            "windows": "winget install -e --id oschwartz10612.Poppler",
            "linux": "sudo apt-get install -y poppler-utils",
            "darwin": "brew install poppler",
        },
    ),
    ToolSpec(
        key="libreoffice", label="LibreOffice", commands=("soffice", "libreoffice"),
        install={
            "windows": "winget install -e --id TheDocumentFoundation.LibreOffice",
            "linux": "sudo apt-get install -y libreoffice",
            "darwin": "brew install --cask libreoffice",
        },
    ),
    ToolSpec(
        key="ghostscript", label="Ghostscript", commands=("gs", "gswin64c", "gswin32c"),
        install={
            "windows": "winget install -e --id ArtifexSoftware.GhostScript",
            "linux": "sudo apt-get install -y ghostscript",
            "darwin": "brew install ghostscript",
        },
    ),
    ToolSpec(
        key="java", label="Java", commands=("java",), version_args=("-version",),
        install={
            "windows": "winget install -e --id EclipseAdoptium.Temurin.21.JDK",
            "linux": "sudo apt-get install -y default-jre",
            "darwin": "brew install temurin",
        },
    ),
)

CORE_TOOLS = ("python", "pip", "git")


@dataclass
class ToolReport:
    key: str
    label: str
    found: bool
    required: bool
    path: Optional[str] = None
    version: Optional[str] = None
    install_hint: Optional[str] = None

    def as_dict(self) -> Dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "found": self.found,
            "required": self.required,
            "path": self.path,
            "version": self.version,
            "install_hint": self.install_hint,
        }


@dataclass
class DoctorResult:
    reports: List[ToolReport]
    platform: str

    @property
    def missing(self) -> List[ToolReport]:
        return [r for r in self.reports if not r.found]

    @property
    def missing_required(self) -> List[ToolReport]:
        return [r for r in self.reports if r.required and not r.found]

    @property
    def clean(self) -> bool:
        return not self.missing_required

    def as_dict(self) -> Dict[str, object]:
        return {
            "generated_at": utc_now_iso(),
            "platform": self.platform,
            "clean": self.clean,
            "missing_required": [r.key for r in self.missing_required],
            "tools": [r.as_dict() for r in self.reports],
        }


def current_platform() -> str:
    sysname = _platform.system().lower()
    if "windows" in sysname:
        return "windows"
    if "darwin" in sysname:
        return "darwin"
    return "linux"


def _probe_version(
    executable: str,
    version_args: Sequence[str],
    run: Callable[..., subprocess.CompletedProcess],
) -> Optional[str]:
    try:
        proc = run(
            [executable, *version_args],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.debug("version probe failed for %s: %s", executable, exc)
        return None
    # java and some tools print the version to stderr.
    text = (proc.stdout or "") + (proc.stderr or "")
    m = _LABELED_VERSION_PATTERN.search(text) or _VERSION_PATTERN.search(text)
    return m.group(1) if m else None


def check_tool(
    spec: ToolSpec,
    platform_key: str,
    which: Callable[[str], Optional[str]] = shutil.which,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> ToolReport:
    for cmd in spec.commands:
        path = which(cmd)
        if path:
            version = _probe_version(path, spec.version_args, run)
            return ToolReport(
                key=spec.key, label=spec.label, found=True,
                required=spec.required, path=path, version=version,
            )
    if spec.fallback_module:
        proc = None
        try:
            proc = run(
                [sys.executable, "-m", spec.fallback_module, "--version"],
                capture_output=True, text=True, timeout=30, check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            log.debug("module fallback failed for %s: %s", spec.key, exc)
        if proc is not None and proc.returncode == 0:
            m = _VERSION_PATTERN.search(proc.stdout or "")
            return ToolReport(
                key=spec.key, label=spec.label, found=True, required=spec.required,
                path=f"{sys.executable} -m {spec.fallback_module}",
                version=m.group(1) if m else None,
            )
    return ToolReport(
        key=spec.key, label=spec.label, found=False, required=spec.required,
        install_hint=spec.install.get(platform_key),
    )


def run_doctor(
    which: Callable[[str], Optional[str]] = shutil.which,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    platform_key: Optional[str] = None,
    core_only: bool = False,
    tools: Sequence[ToolSpec] = TOOLS,
) -> DoctorResult:
    platform_key = platform_key or current_platform()
    selected = [t for t in tools if not core_only or t.key in CORE_TOOLS]
    reports = [check_tool(spec, platform_key, which=which, run=run) for spec in selected]
    return DoctorResult(reports=reports, platform=platform_key)


def write_report(result: DoctorResult, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.as_dict(), indent=2) + "\n", encoding="utf-8")
    return path


def install_missing(
    result: DoctorResult,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> List[Tuple[str, str, int]]:
    """Attempt to install every missing tool with its platform command.

    Installs add software; they never remove or overwrite user data, so they do
    not require ``--confirm``. Returns ``(tool, command, returncode)`` triples.
    """
    attempts: List[Tuple[str, str, int]] = []
    for report in result.missing:
        cmd = report.install_hint
        if not cmd:
            attempts.append((report.key, "<no install command for this platform>", 1))
            continue
        log.info("installing %s: %s", report.label, cmd)
        try:
            proc = run(cmd, shell=True, check=False)
            rc = proc.returncode
        except (OSError, subprocess.SubprocessError) as exc:
            log.error("install of %s failed: %s", report.label, exc)
            rc = 1
        attempts.append((report.key, cmd, rc))
    return attempts


def format_report(result: DoctorResult) -> str:
    lines = [f"databossx doctor — platform: {result.platform}"]
    for r in result.reports:
        if r.found:
            version = r.version or "version unknown"
            lines.append(f"  [ok]      {r.label:<20} {version:<18} {r.path}")
        else:
            tag = "MISSING" if r.required else "missing (optional)"
            lines.append(f"  [{tag}] {r.label:<20} install: {r.install_hint or 'n/a'}")
    lines.append(
        "  result: CLEAN" if result.clean
        else f"  result: NOT CLEAN — missing required: "
             f"{', '.join(r.key for r in result.missing_required)}"
    )
    return "\n".join(lines)
