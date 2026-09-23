from __future__ import annotations

from databossx.database import DataBossDatabase
from databossx.governor.cycle import ISSUE94_SEEDS, run_synthetic_cycle
from databossx.governor.envelope import compile_envelope
from databossx.governor.inventory import census_repository
from databossx.governor.lease import StaleWriter, acquire_lease, assert_lease
from databossx.governor.models import ImprovementProposal
from databossx.governor.ranker import rank_proposals
from databossx.governor.tournament import judge_folders


def test_ranker_vetoes_release_and_prefers_issue94():
    ranked = rank_proposals(list(ISSUE94_SEEDS))
    assert ranked[-1].status == "vetoed"
    assert "external_release" in ranked[-1].vetoes
    assert ranked[0].proposal_id.startswith("issue94-")


def test_envelope_hash_is_stable(tmp_path):
    proposal = rank_proposals(list(ISSUE94_SEEDS))[0]
    first = compile_envelope(proposal, base_commit="abc", inputs=["a"], tests=["t"])
    second = compile_envelope(proposal, base_commit="abc", inputs=["a"], tests=["t"])
    assert first.envelope_hash == second.envelope_hash
    third = compile_envelope(proposal, base_commit="def", inputs=["a"], tests=["t"])
    assert third.envelope_hash != first.envelope_hash


def test_stale_writer_rejected(tmp_path):
    db = DataBossDatabase(tmp_path / "g.db")
    db.initialize()
    fence = acquire_lease(db, "repo:governor", "worker-a")
    try:
        acquire_lease(db, "repo:governor", "worker-b")
        raised = False
    except StaleWriter:
        raised = True
    assert raised
    assert_lease(db, "repo:governor", "worker-a", fence)


def test_synthetic_cycle_and_census(tmp_path):
    (tmp_path / "tests").mkdir()
    for name in (
        "test_issue94_integrity.py",
        "test_governor.py",
        "test_backend_security.py",
        "test_publication_policy.py",
    ):
        (tmp_path / "tests" / name).write_text("# synthetic\n", encoding="utf-8")
    receipt = run_synthetic_cycle(tmp_path, base_commit="test")
    assert receipt.outcome == "CYCLE_ACCEPTED_FOR_INDEPENDENT_REVIEW"
    assert receipt.payload["client_bytes_mutated"] == "NO"
    census = census_repository(tmp_path)
    assert census["tests"] >= 4
    assert census["unknown_is_not_zero"] is True


def test_tournament_blocks_clientish_folder(tmp_path):
    good = tmp_path / "_AI_GOOD__X"
    bad = tmp_path / "_AI_BAD__X"
    good.mkdir()
    bad.mkdir()
    (good / "README.md").write_text("Governor notes. No fabrication. UNKNOWN is not ZERO.", encoding="utf-8")
    (good / "RECEIPT.md").write_text("CLIENT_BYTES_MUTATED=NO EXTERNAL_RELEASE=NO", encoding="utf-8")
    (bad / "README.md").write_text("see drive.google.com/file/d/abc", encoding="utf-8")
    (bad / "RECEIPT.md").write_text("ok", encoding="utf-8")
    result = judge_folders(tmp_path)
    assert result["winner"] == good.name
    assert any(row["blocked"] for row in result["scorecards"] if row["folder"] == bad.name)
