from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]

FORBIDDEN_SNIPPETS = (
    "AIza",
    "sk-proj-",
    "BEGIN PRIVATE KEY",
    "drive.google.com/file/d/",
)


def test_examples_are_synthetic_only():
    examples = REPO / "examples"
    manifests = list(examples.rglob("*.json"))
    assert manifests
    for path in manifests:
        text = path.read_text(encoding="utf-8")
        assert "SYNTHETIC" in text or "FICTIONAL" in text


def test_current_tree_has_no_live_secret_markers():
    scanned = []
    for path in (*REPO.glob("*.md"), *REPO.glob("*.py"), *(REPO / "src").rglob("*.py")):
        if path.name.startswith("."):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for snippet in FORBIDDEN_SNIPPETS:
            assert snippet not in text, f"{path} contains forbidden snippet"
        scanned.append(path)
    assert scanned


def test_no_client_project_trees_in_public_repo():
    assert not (REPO / "private_projects").exists()
    assert not list(REPO.glob("projects/OK-*"))
