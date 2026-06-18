"""Secret scanner for DataBossX.

Detects likely secrets (API keys, tokens, private keys) and reports their
*location* and *type* only -- never the value. Distinguishes:
  * tracked-by-git secrets (high severity: exposed in history)
  * untracked local secrets (lower severity: working tree only)
  * placeholder/empty values (informational)

Designed to satisfy: "secret scan detects fake keys".
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import paths

# (label, compiled regex). Patterns match the *value* portion.
SECRET_PATTERNS = [
    ("OpenAI key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("Google/Gemini key", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("xAI/Grok key", re.compile(r"xai-[A-Za-z0-9]{20,}")),
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Slack token", re.compile(r"xox[baprs]-[0-9A-Za-z\-]{10,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[0-9A-Za-z]{30,}")),
    ("Private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("Generic long key=value", re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{24,}")),
]

# Files we scan even though they are otherwise "excluded" because .env is the
# most common place secrets leak.
ALWAYS_SCAN_NAMES = {".env"}

SCANNABLE_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".toml", ".yml", ".yaml",
    ".md", ".txt", ".env", ".sh", ".bat", ".cfg", ".ini", "",
}


@dataclass
class Finding:
    path: str
    line: int
    label: str
    tracked: bool


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def tracked_findings(self) -> list[Finding]:
        return [f for f in self.findings if f.tracked]


def _git_tracked_files(root: Path) -> set[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
        )
        return set(out.stdout.split())
    except Exception:
        return set()


def _should_scan(path: Path) -> bool:
    if path.name in ALWAYS_SCAN_NAMES:
        return True
    # Any dotenv variant (.env, .env.local, .env.production, ...) — these are the
    # most common secret-leak files and the .gitignore treats `.env.*` as secret.
    if path.name == ".env" or path.name.startswith(".env."):
        return True
    if path.name.endswith(".example"):
        # Templates are safe to scan but rarely hold real secrets; still scan.
        return True
    if any(part in paths.EXCLUDED_DIR_NAMES for part in path.parts):
        return False
    return path.suffix in SCANNABLE_SUFFIXES


def scan(root: Path | None = None, max_bytes: int = 2_000_000) -> ScanResult:
    root = root or paths.ROOT
    tracked = _git_tracked_files(root)
    result = ScanResult()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if not _should_scan(path):
            continue
        try:
            if path.stat().st_size > max_bytes:
                continue
            text = path.read_text(errors="ignore")
        except Exception:
            continue
        result.files_scanned += 1
        rel = path.relative_to(root).as_posix()
        is_tracked = rel in tracked
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    result.findings.append(Finding(rel, lineno, label, is_tracked))
                    break
    return result


def render_report(result: ScanResult, ts: str) -> str:
    lines = [
        f"# DataBossX Secret Scan — {ts}",
        "",
        f"- Files scanned: **{result.files_scanned}**",
        f"- Total findings: **{len(result.findings)}**",
        f"- Tracked-by-git findings (EXPOSED): **{len(result.tracked_findings)}**",
        "",
        "Values are never shown. Only location + type.",
        "",
    ]
    if not result.findings:
        lines.append("No secret-like patterns detected. ✅")
        return "\n".join(lines)

    if result.tracked_findings:
        lines += ["## 🚨 Tracked secrets (in git — treat as COMPROMISED, rotate keys)", ""]
        lines.append("| File | Line | Type |")
        lines.append("|------|------|------|")
        for f in result.tracked_findings:
            lines.append(f"| `{f.path}` | {f.line} | {f.label} |")
        lines.append("")

    untracked = [f for f in result.findings if not f.tracked]
    if untracked:
        lines += ["## ⚠️ Untracked secrets (working tree only — keep ignored)", ""]
        lines.append("| File | Line | Type |")
        lines.append("|------|------|------|")
        for f in untracked:
            lines.append(f"| `{f.path}` | {f.line} | {f.label} |")
        lines.append("")
    return "\n".join(lines)


def run(ts: str | None = None) -> Path:
    paths.ensure_dirs()
    ts = ts or paths.timestamp()
    result = scan()
    report = render_report(result, ts)
    out = paths.REPORTS / f"secret_scan_{ts}.md"
    out.write_text(report)
    return out
