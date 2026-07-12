import json
import struct
import zipfile
from pathlib import Path

import openpyxl
import pytest

from databoss_title_factory.cli import EXIT_INPUT_ERROR, EXIT_OK, main
from databoss_title_factory.config import ConfigError, load_config
from databoss_title_factory.core import latest_run
from databoss_title_factory.model_tournament import (
    CandidateOutput,
    ProviderPolicy,
    TournamentConfig,
    enforce_provider_policy,
    score_candidates_blind,
)
from databoss_title_factory.release import (
    ReleaseContext,
    ReleaseStatus,
    evaluate_release,
)
from databoss_title_factory.security import (
    EvidenceStatus,
    SecurityError,
    ZipLimits,
    resolve_allowed_path,
    sanitize_filename,
    validate_zip,
    verify_signature,
)
from databoss_title_factory.title_interest import (
    BurdenBasis,
    EvidenceValue,
    calculate_title_interest,
)


def test_evidence_status_contract_is_exact():
    assert [item.name for item in EvidenceStatus] == [
        "VERIFIED",
        "DIRECTLY_OBSERVED",
        "EXTRACTED_UNVERIFIED",
        "INFERRED",
        "ASSUMED",
        "ESTIMATED",
        "CONFLICTED",
        "MISSING",
        "NOT_APPLICABLE",
        "REJECTED",
    ]


def test_safe_path_rejects_traversal_and_symlink_escape(tmp_path: Path):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    evidence = allowed / "evidence.pdf"
    evidence.write_bytes(b"%PDF-1.7\n")
    assert resolve_allowed_path(evidence, [allowed]) == evidence
    with pytest.raises(SecurityError):
        resolve_allowed_path(allowed / ".." / "outside", [allowed])
    (allowed / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(SecurityError):
        resolve_allowed_path(allowed / "escape", [allowed])


def test_zip_validation_rejects_zip_slip_encryption_and_bomb(tmp_path: Path):
    slip = tmp_path / "slip.zip"
    with zipfile.ZipFile(slip, "w") as archive:
        archive.writestr("../escape.txt", "bad")
    with pytest.raises(SecurityError, match="unsafe ZIP"):
        validate_zip(slip)

    bomb = tmp_path / "bomb.zip"
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("zeros.txt", b"0" * 100_000)
    with pytest.raises(SecurityError, match="ratio"):
        validate_zip(bomb, limits=ZipLimits(max_compression_ratio=2))

    encrypted = tmp_path / "encrypted-flag.zip"
    with zipfile.ZipFile(encrypted, "w") as archive:
        archive.writestr("evidence.txt", "content")
    payload = bytearray(encrypted.read_bytes())
    local = payload.index(b"PK\x03\x04")
    central = payload.index(b"PK\x01\x02")
    struct.pack_into("<H", payload, local + 6, struct.unpack_from("<H", payload, local + 6)[0] | 1)
    struct.pack_into(
        "<H", payload, central + 8, struct.unpack_from("<H", payload, central + 8)[0] | 1
    )
    encrypted.write_bytes(payload)
    with pytest.raises(SecurityError, match="encrypted"):
        validate_zip(encrypted)


def test_filename_and_signature_checks(tmp_path: Path):
    assert sanitize_filename("../../CON?.pdf") == "CON_.pdf"
    assert sanitize_filename("CON.pdf") == "_CON.pdf"
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    assert verify_signature(pdf).valid
    fake = tmp_path / "source.png"
    fake.write_bytes(b"%PDF-1.7\n")
    assert not verify_signature(fake).valid


def _ev(value, ref, status=EvidenceStatus.VERIFIED):
    return EvidenceValue(value=value, evidence_refs=(ref,), status=status)


def test_exact_title_interest_respects_burden_basis_and_trace():
    gross_basis = calculate_title_interest(
        _ev("1/2", "lease#p1"),
        _ev("1/8", "lease#p2"),
        _ev("160", "tract#p1"),
        BurdenBasis.GROSS_PRODUCTION,
    )
    assert gross_basis.net_revenue_interest.fraction_display == "3/8"
    assert gross_basis.net_leasehold_acres.fraction_display == "80"
    assert (gross_basis.numerator, gross_basis.denominator) == (3, 8)
    assert gross_basis.trace

    wi_basis = calculate_title_interest(
        _ev("1/2", "lease#p1"),
        _ev("1/8", "lease#p2"),
        _ev("160", "tract#p1"),
        BurdenBasis.WORKING_INTEREST,
    )
    assert wi_basis.net_revenue_interest.fraction_display == "7/16"


def test_title_interest_blocks_missing_evidence_ambiguity_and_negative_nri():
    missing_ref = calculate_title_interest(
        EvidenceValue("1/2", ()),
        _ev("1/8", "lease#p2"),
        _ev("160", "tract#p1"),
        BurdenBasis.GROSS_PRODUCTION,
    )
    assert missing_ref.blocked
    ambiguous = calculate_title_interest(
        _ev("about half", "lease#p1"),
        _ev("1/8", "lease#p2"),
        _ev("160", "tract#p1"),
        BurdenBasis.GROSS_PRODUCTION,
    )
    assert ambiguous.blocked
    assumed = calculate_title_interest(
        _ev("1/2", "lease#p1", EvidenceStatus.ASSUMED),
        _ev("1/8", "lease#p2"),
        _ev("160", "tract#p1"),
        BurdenBasis.GROSS_PRODUCTION,
    )
    assert assumed.blocked
    negative = calculate_title_interest(
        _ev("1/8", "lease#p1"),
        _ev("1/4", "lease#p2"),
        _ev("160", "tract#p1"),
        BurdenBasis.GROSS_PRODUCTION,
    )
    assert negative.blocked


def _complete_release(**changes):
    values = {
        "inventory_complete": True,
        "approvals_complete": True,
        "source_scope_limited": False,
    }
    values.update(changes)
    return ReleaseContext(**values)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"inventory_complete": False}, "inventory"),
        ({"corrupt_sources": True}, "corrupt"),
        ({"evidence_conflicts": True}, "conflicts"),
        ({"missing_exhibits": True}, "exhibits"),
        ({"unresolved_owner": True}, "owner"),
        ({"acreage_mismatch": True}, "acreage"),
        ({"negative_values": True}, "negative"),
        ({"forced_balance": True}, "forced"),
        ({"tract_overlaps": True}, "overlap"),
        ({"unsupported_working_interest": True}, "working interest"),
        ({"workbook_external_links": True}, "external links"),
        ({"template_mismatch": True}, "template"),
        ({"critical_open_items": 1}, "critical"),
    ],
)
def test_release_gates_block_each_material_defect(change, reason):
    decision = evaluate_release(_complete_release(**change))
    assert decision.status is ReleaseStatus.BLOCKED
    assert reason in " ".join(decision.blockers)


def test_source_limited_internal_status_never_allows_external_release():
    internal = evaluate_release(
        _complete_release(
            source_scope_limited=True,
            external_release_requested=False,
            internal_source_limited_approved=True,
        )
    )
    assert internal.status is ReleaseStatus.SOURCE_LIMITED
    assert not internal.external_release_allowed
    assert evaluate_release(ReleaseContext()).status is ReleaseStatus.BLOCKED


def test_release_lifecycle_uses_required_values_and_separates_technical_approval():
    assert [item.value for item in ReleaseStatus] == [
        "DRAFT",
        "INTERNAL_WORKING",
        "SOURCE_LIMITED",
        "REVIEW_REQUIRED",
        "BLOCKED",
        "READY_FOR_EXAMINER",
        "APPROVED_FOR_DELIVERY",
        "DELIVERED",
    ]
    examiner = evaluate_release(_complete_release(approvals_complete=False))
    assert examiner.status is ReleaseStatus.READY_FOR_EXAMINER
    assert not examiner.external_release_allowed
    approved = evaluate_release(_complete_release())
    assert approved.status is ReleaseStatus.APPROVED_FOR_DELIVERY
    assert approved.external_release_allowed
    delivered = evaluate_release(_complete_release(delivered=True))
    assert delivered.status is ReleaseStatus.DELIVERED
    assert not delivered.external_release_allowed
    limited_unapproved = evaluate_release(
        _complete_release(
            source_scope_limited=True,
            external_release_requested=False,
            internal_source_limited_approved=False,
        )
    )
    assert limited_unapproved.status is ReleaseStatus.REVIEW_REQUIRED


def test_tournament_enforces_policy_scores_blind_and_preserves_conflicts():
    policy = ProviderPolicy(
        "local",
        enabled=True,
        allowed_modalities=frozenset({"text"}),
        max_pages=2,
        max_cost=1.0,
        manual_approval_required=True,
    )
    assert not enforce_provider_policy(
        policy,
        modality="pdf",
        page_count=3,
        estimated_cost=2,
        manual_approval=False,
    ).allowed
    config = TournamentConfig((policy,), required_schema_fields=("owner", "nri"))
    candidates = [
        CandidateOutput(
            "one",
            "local",
            "model-a",
            "text",
            1,
            0.1,
            {"owner": "A", "nri": "1/2"},
            ("source#1",),
            ("source#1",),
            True,
            True,
            True,
            True,
        ),
        CandidateOutput(
            "two",
            "local",
            "model-b",
            "text",
            1,
            0.1,
            {"owner": "B", "nri": "1/2"},
            ("source#1",),
            ("source#1",),
            True,
            True,
            True,
            True,
        ),
        CandidateOutput(
            "three",
            "disabled",
            "model-c",
            "text",
            1,
            0.0,
            {"owner": "B", "nri": "1/2"},
        ),
    ]
    result = score_candidates_blind(
        config, candidates, verified_evidence_refs=("source#1",)
    )
    assert result.truth_established is False
    assert result.conflicts[0].field == "owner"
    assert result.conflicts[0].status == "UNRESOLVED"
    assert result.agreements["nri"] == "1/2"
    assert next(score for score in result.scores if score.candidate_id == "three").eligible is False
    assert all(score.blind_id.startswith("BLIND-") for score in result.scores)


def test_sample_config_expands_environment_and_keeps_external_disabled(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    config_path = (
        Path(__file__).parents[1]
        / "databoss_title_factory"
        / "sample_config"
        / "beckham_section_32.json"
    )
    config = load_config(
        config_path,
        environment={"DATABOSS_SECTION32_SOURCE_ROOT": str(source)},
    )
    assert config.source_root == source
    assert not config.external_providers_enabled
    assert any(
        item["name"] == "open_items_working_count" and item["value"] == 21
        for item in config.data["expected_counts"]
    )
    assert all(not item.get("ownership_claim", False) for item in config.data["control_facts"])
    with pytest.raises(ConfigError):
        load_config(config_path, environment={})


def test_cli_health_inventory_and_path_blocking(tmp_path: Path, capsys):
    assert main(["health"]) == EXIT_OK
    project = tmp_path / "project"
    project.mkdir()
    (project / "source.txt").write_text("evidence", encoding="utf-8")
    assert main(
        ["inventory", "--root", str(project), "--allow-root", str(tmp_path)]
    ) == EXIT_OK
    assert (latest_run(project).output_dir / "latest_run.txt").is_file()
    assert not (project / "DataBoss_Title_Factory_Output").exists()
    outside = tmp_path.parent
    assert main(
        ["inventory", "--root", str(outside), "--allow-root", str(project)]
    ) == EXIT_INPUT_ERROR
    assert "INPUT_ERROR" in capsys.readouterr().out
