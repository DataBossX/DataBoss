from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


try:  # pytest is optional for the stdlib-only subsystems in this repo
    import pytest
except ImportError:  # pragma: no cover
    pytest = None


if pytest is not None:

    @pytest.fixture
    def frozen_clock():
        from databossx.command_brain.util import FrozenClock

        return FrozenClock()

    @pytest.fixture
    def runtime(tmp_path, frozen_clock):
        """A Command Brain runtime on a throwaway database with a frozen clock."""
        from databossx.command_brain.runtime import CommandBrainRuntime

        return CommandBrainRuntime(
            tmp_path / "command_brain.db",
            clock=frozen_clock,
            id_seed="test-seed",
            requesting_user="ryan",
            project_id="sec32_synthetic",
        )

    @pytest.fixture
    def brain(runtime):
        from databossx.command_brain.service import CommandBrain

        service = CommandBrain(runtime)
        service.start_conversation("text", "sec32_synthetic")
        return service
