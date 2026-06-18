"""Lightweight sanity checks that don't require a running backend.

These run in CI (`pytest`) where the live DataBossX deployment is unavailable,
so they must not import the app or make network calls.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _parse_exact_pins(requirements_text):
    """Return {package_name: {pinned_versions}} for lines using `==`."""
    pins = {}
    for raw in requirements_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        # Drop environment markers, e.g. `; sys_platform != 'win32'`.
        version = version.split(";")[0].strip()
        pins.setdefault(name.strip().lower(), set()).add(version)
    return pins


def test_requirements_have_no_conflicting_pins():
    """A package must not be pinned to two different `==` versions.

    Regression guard for the duplicate `tenacity==8.2.3` / `tenacity==9.0.0`
    pins that broke `pip install -r requirements.txt` with ResolutionImpossible.
    """
    pins = _parse_exact_pins((REPO_ROOT / "requirements.txt").read_text())
    conflicts = {name: sorted(v) for name, v in pins.items() if len(v) > 1}
    assert not conflicts, f"Conflicting version pins in requirements.txt: {conflicts}"
