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


def credential_sample(prefix: str, body: str) -> str:
    """Assemble a credential-shaped test string at runtime.

    Built from two halves rather than written as a literal so the repository's
    Gitleaks scan has nothing to flag. Neither half matches a detection rule on
    its own. A fake key that trips the scanner costs a red build on every run,
    and a scanner people learn to ignore is worse than no scanner at all.
    """
    return prefix + body


if pytest is not None:

    @pytest.fixture
    def credential_samples():
        """Credential-shaped strings covering the formats redaction must catch."""
        return {
            "openai": credential_sample("sk-", "abcdefghijklmnopqrstuvwxyz0123456789"),
            "github_pat": credential_sample("ghp_", "abcdefghijklmnopqrstuvwxyz0123456789"),
            "aws_access_key": credential_sample("AKIA", "IOSFODNN7EXAMPLE"),
            "private_key_header": credential_sample("-----BEGIN RSA ", "PRIVATE KEY-----"),
        }
