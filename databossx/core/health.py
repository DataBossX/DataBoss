"""Health check for DataBossX.

Verifies the runtime, key dependencies, directory layout, and surfaces the
top safety risks without printing any secret values.
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

from . import paths


def _dep(name: str) -> tuple[str, bool, str]:
    try:
        mod = __import__(name)
        return name, True, getattr(mod, "__version__", "?")
    except Exception:
        return name, False, "-"


def collect() -> dict:
    deps = [_dep(n) for n in ("openpyxl", "pandas")]
    dirs = {d.name: d.exists() for d in paths.ALL_ARTIFACT_DIRS}
    # Cheap risk flag: tracked .env presence.
    tracked_env = []
    for env in paths.ROOT.rglob(".env"):
        if ".git" in env.parts:
            continue
        tracked_env.append(env.relative_to(paths.ROOT).as_posix())
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "deps": deps,
        "dirs": dirs,
        "env_files_present": tracked_env,
    }


def render(info: dict, ts: str) -> str:
    lines = [
        f"# DataBossX Health Check — {ts}",
        "",
        f"- Python: `{info['python']}`",
        f"- Platform: `{info['platform']}`",
        "",
        "## Dependencies",
        "",
        "| Package | Present | Version |",
        "|---------|---------|---------|",
    ]
    for name, ok, ver in info["deps"]:
        lines.append(f"| {name} | {'✅' if ok else '❌'} | {ver} |")
    lines += ["", "## Artifact directories", ""]
    for name, ok in info["dirs"].items():
        lines.append(f"- `{name}/`: {'✅' if ok else '❌ missing'}")
    lines += ["", "## Safety flags", ""]
    if info["env_files_present"]:
        lines.append("- ⚠️ `.env` files present in tree (must be gitignored, never committed):")
        for e in info["env_files_present"]:
            lines.append(f"  - `{e}`")
    else:
        lines.append("- ✅ no `.env` files found in working tree")
    overall = all(ok for _, ok, _ in info["deps"])
    lines += ["", f"**Overall: {'HEALTHY ✅' if overall else 'DEGRADED ⚠️'}**", ""]
    return "\n".join(lines)


def run(ts: str | None = None) -> Path:
    paths.ensure_dirs()
    ts = ts or paths.timestamp()
    info = collect()
    out = paths.REPORTS / f"health_check_{ts}.md"
    out.write_text(render(info, ts))
    return out
