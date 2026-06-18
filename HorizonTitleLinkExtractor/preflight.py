"""
preflight.py
============
A "doctor" that checks everything is ready BEFORE a long automation run, and
prints a clear PASS/WARN/FAIL checklist a non-coder can act on.

Run via:  RUN_DOCTOR.bat   (or:  python title_link_extractor.py --doctor)

Critical failures (missing OpenAI key, unreadable config, missing login) make
the full review refuse to start; warnings are informational.
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
_ICON = {PASS: "[ OK ]", WARN: "[WARN]", FAIL: "[FAIL]"}


def _check_python() -> Tuple[str, str]:
    v = sys.version_info
    if v >= (3, 11):
        return PASS, f"Python {v.major}.{v.minor}.{v.micro}"
    return FAIL, f"Python {v.major}.{v.minor} found - need 3.11+"


def _check_packages() -> List[Tuple[str, str]]:
    results = []
    required = ["openpyxl", "yaml", "pydantic", "dotenv", "tenacity"]
    optional = {
        "playwright": "browser automation (required to capture documents)",
        "openai": "primary vision extractor",
        "google.generativeai": "optional Gemini validator",
        "anthropic": "optional Claude validator",
        "googleapiclient": "optional Google Drive API mode",
    }
    for mod in required:
        try:
            importlib.import_module(mod)
            results.append((PASS, f"package '{mod}' importable"))
        except Exception:
            results.append((FAIL, f"package '{mod}' MISSING - run INSTALL.bat"))
    for mod, why in optional.items():
        try:
            importlib.import_module(mod)
            results.append((PASS, f"package '{mod}' importable ({why})"))
        except Exception:
            sev = FAIL if mod == "playwright" else WARN
            results.append((sev, f"package '{mod}' missing - {why}"))
    return results


def _check_config() -> List[Tuple[str, str]]:
    out = []
    cfg_path = os.path.join(HERE, "config.yaml")
    if not os.path.exists(cfg_path):
        return [(FAIL, "config.yaml not found")]
    try:
        import yaml

        from config_schema import validate_config

        with open(cfg_path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        cfg = validate_config(raw)
        out.append((PASS, "config.yaml parses and validates"))
        if cfg.get("apply_corrections"):
            out.append((WARN, "apply_corrections=TRUE - original cells WILL be overwritten"))
        else:
            out.append((PASS, "apply_corrections=false (review only - safe default)"))
        return out
    except Exception as exc:
        return [(FAIL, f"config.yaml invalid: {exc}")]


def _check_env() -> List[Tuple[str, str]]:
    out = []
    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(HERE, ".env"))
    except Exception:
        pass
    if not os.path.exists(os.path.join(HERE, ".env")):
        out.append((WARN, ".env file not found - copy .env.example to .env and add keys"))
    if os.getenv("OPENAI_API_KEY"):
        out.append((PASS, "OPENAI_API_KEY is set (primary extractor)"))
    else:
        out.append((FAIL, "OPENAI_API_KEY is NOT set - primary extractor will not run"))
    out.append(
        (PASS if os.getenv("GEMINI_API_KEY") else WARN,
         f"GEMINI_API_KEY {'set' if os.getenv('GEMINI_API_KEY') else 'not set (validator disabled)'}")
    )
    out.append(
        (PASS if os.getenv("ANTHROPIC_API_KEY") else WARN,
         f"ANTHROPIC_API_KEY {'set' if os.getenv('ANTHROPIC_API_KEY') else 'not set (validator disabled)'}")
    )
    return out


def _check_drive() -> List[Tuple[str, str]]:
    sync = os.getenv("GOOGLE_DRIVE_LOCAL_SYNC_PATH", "").strip()
    if sync:
        if os.path.isdir(sync):
            return [(PASS, f"Drive Desktop mode: {sync}")]
        return [(FAIL, f"GOOGLE_DRIVE_LOCAL_SYNC_PATH set but not found: {sync}")]
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET_JSON"):
        return [(PASS, "Drive API mode credentials present")]
    return [(WARN, "No Drive upload configured - output stays local (manual upload instructions printed)")]


def _check_auth() -> List[Tuple[str, str]]:
    import yaml

    cfg_path = os.path.join(HERE, "config.yaml")
    auth = ".auth/county_state.json"
    try:
        with open(cfg_path, "r", encoding="utf-8") as fh:
            auth = (yaml.safe_load(fh) or {}).get("auth_state_path", auth)
    except Exception:
        pass
    full = os.path.join(HERE, auth)
    if os.path.exists(full):
        return [(PASS, f"county login session present ({auth})")]
    return [(FAIL, f"no county login session ({auth}) - run RUN_LOGIN_SETUP.bat")]


def _check_folders() -> List[Tuple[str, str]]:
    out = []
    for d in ["input", "output", "logs", "temp", "debug", ".auth"]:
        p = os.path.join(HERE, d)
        if os.path.isdir(p):
            out.append((PASS, f"folder '{d}/' exists"))
        else:
            out.append((WARN, f"folder '{d}/' missing - INSTALL.bat creates it"))
    return out


def run_doctor() -> int:
    """Print the checklist. Return 0 if no critical FAILs, else 1."""
    sections = [
        ("Python", [_check_python()]),
        ("Packages", _check_packages()),
        ("Configuration", _check_config()),
        ("API keys (.env)", _check_env()),
        ("Google Drive", _check_drive()),
        ("County login", _check_auth()),
        ("Folders", _check_folders()),
    ]
    fails = 0
    print("\n=================== PREFLIGHT DOCTOR ===================\n")
    for title, results in sections:
        print(f"  {title}:")
        for sev, msg in results:
            if sev == FAIL:
                fails += 1
            print(f"    {_ICON[sev]} {msg}")
        print()
    print("=======================================================")
    if fails:
        print(f"\n{fails} critical issue(s) found. Fix the [FAIL] items above before running.\n")
        return 1
    print("\nAll critical checks passed. You are ready to run RUN_TEST_5_ROWS.bat.\n")
    return 0


if __name__ == "__main__":
    sys.exit(run_doctor())
