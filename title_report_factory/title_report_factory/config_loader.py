"""config_loader -- load and validate the run configuration."""
from __future__ import annotations

import json
import os
from pathlib import Path


REQUIRED_TOP_KEYS = ["subject_property", "inputs", "output"]


def load_config(config_path: str) -> dict:
    p = Path(config_path)
    if not p.is_absolute():
        # resolve relative to the project root (parent of the package dir)
        root = Path(__file__).resolve().parent.parent
        p = (root / config_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with open(p, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    missing = [k for k in REQUIRED_TOP_KEYS if k not in cfg]
    if missing:
        raise ValueError(f"Config missing required keys: {missing}")

    root = p.parent.parent  # project root = configs/.. typically
    cfg["_project_root"] = str(root)
    cfg["_config_path"] = str(p)

    # Resolve input/output directories relative to project root.
    input_dir = Path(cfg["inputs"].get("input_dir", "inputs"))
    output_dir = Path(cfg["output"].get("output_dir", "outputs"))
    cfg["_input_dir"] = str(input_dir if input_dir.is_absolute() else root / input_dir)
    cfg["_output_dir"] = str(output_dir if output_dir.is_absolute() else root / output_dir)
    os.makedirs(cfg["_output_dir"], exist_ok=True)
    return cfg


def input_path(cfg: dict, key: str) -> str | None:
    """Return absolute path of a named input file, if it exists."""
    name = cfg.get("inputs", {}).get(key)
    if not name:
        return None
    path = Path(cfg["_input_dir"]) / name
    return str(path) if path.exists() else None
