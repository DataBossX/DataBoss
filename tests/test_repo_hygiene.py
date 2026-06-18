"""Repo hygiene regression tests (pure stdlib — always runnable).

These lock in the security/hygiene fixes applied during the upgrade so they
cannot silently regress.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _git_tracked():
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True
    )
    return out.stdout.splitlines()


def test_no_secrets_or_db_tracked_by_git():
    tracked = _git_tracked()
    offenders = [
        f for f in tracked
        if (f.endswith(".env") and not f.endswith(".env.example"))
        or f.endswith((".key", ".pem", ".db", ".sqlite", ".sqlite3"))
    ]
    assert offenders == [], f"secret-like files tracked: {offenders}"


def test_requirements_has_no_stdlib_sqlite3_pin():
    body = (ROOT / "backend" / "requirements.txt").read_text()
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert not stripped.lower().startswith("sqlite3"), (
            "sqlite3 is stdlib and must not be a pip requirement"
        )


def test_env_examples_exist():
    for rel in [".env.example", "backend/.env.example",
                "frontend/.env.example"]:
        assert (ROOT / rel).exists(), f"missing {rel}"


def test_gitignore_blocks_env_and_db():
    gi = (ROOT / ".gitignore").read_text()
    assert ".env" in gi
    assert "*.db" in gi


def test_no_pip_redirect_artifact_files():
    # Files like backend/=0.7.0 come from a botched 'pip install x>=y' redirect.
    artifacts = list(ROOT.glob("**/=*"))
    artifacts = [a for a in artifacts if ".git" not in a.parts]
    assert artifacts == [], f"stray pip-redirect artifacts: {artifacts}"
