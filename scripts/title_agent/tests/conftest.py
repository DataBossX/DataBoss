"""Pytest fixtures for the Title Agent test suite.

The test functions take a ``tmp: Path`` parameter and each module can also be
run directly (``python -m scripts.title_agent.tests.test_x``) via its own
``_run_all`` harness. This fixture makes the same tests collectable by pytest
by aliasing the built-in ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp(tmp_path: Path) -> Path:
    return tmp_path
