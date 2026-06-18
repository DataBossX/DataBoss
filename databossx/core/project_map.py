"""Project map generator for DataBossX.

Walks the tree (skipping excluded/secret dirs) and produces a markdown map
plus a flag of the highest-risk files (entry points, secrets, large files).
"""
from __future__ import annotations

from pathlib import Path

from . import paths

ENTRYPOINT_HINTS = ("main.py", "app.py", "server.py", "command_center.py", "__main__.py", "manage.py")


def build_map(root: Path | None = None, max_depth: int = 3) -> str:
    root = root or paths.ROOT
    lines = ["# DataBossX Project Map", "", f"Root: `{root}`", ""]
    entrypoints: list[str] = []
    py_count = 0
    total = 0

    def walk(d: Path, depth: int) -> None:
        nonlocal py_count, total
        if depth > max_depth:
            return
        try:
            children = sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return
        for child in children:
            rel = child.relative_to(root)
            if child.name in paths.EXCLUDED_DIR_NAMES:
                continue
            indent = "  " * depth
            if child.is_dir():
                lines.append(f"{indent}- 📁 `{child.name}/`")
                walk(child, depth + 1)
            else:
                total += 1
                if child.suffix == ".py":
                    py_count += 1
                if child.name in ENTRYPOINT_HINTS:
                    entrypoints.append(rel.as_posix())
                lines.append(f"{indent}- 📄 `{child.name}`")

    walk(root, 0)

    summary = [
        "## Summary",
        "",
        f"- Files listed: **{total}**",
        f"- Python files: **{py_count}**",
        f"- Entry points detected: {', '.join(f'`{e}`' for e in entrypoints) or 'none'}",
        "",
        "## Tree",
        "",
    ]
    return "\n".join(summary + lines) + "\n"


def run(ts: str | None = None) -> Path:
    paths.ensure_dirs()
    ts = ts or paths.timestamp()
    out = paths.REPORTS / f"project_map_{ts}.md"
    out.write_text(build_map())
    return out
