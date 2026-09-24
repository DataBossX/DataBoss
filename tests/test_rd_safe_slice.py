from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

from databossx_rd.constants import (
    DOCLING_PINNED_VERSION,
    LOOPBACK_HOST,
    MINERU_PINNED_VERSION,
    N8N_MIN_STABLE_LABEL,
    UNKNOWN,
)
from databossx_rd.loopback_http import (
    HttpResult,
    LoopbackClient,
    LoopbackHttpError,
    assert_allowed_path,
    assert_loopback_url,
)
from databossx_rd.n8n_guard import evaluate_n8n_safety, probe_n8n
from databossx_rd.ollama_inventory import probe_ollama, thinking_from_show
from databossx_rd.parser_bench import (
    load_bench_spec,
    measure_extractor,
    run_parser_bench,
    sha256_file,
    validate_bench_spec,
)
from databossx_rd.writer import IsolationError, WriterConflict, exclusive_writer


REPO_ROOT = Path(__file__).resolve().parents[1]


def _result(url: str, payload: dict, status: int = 200) -> HttpResult:
    return HttpResult(
        ok=200 <= status < 300,
        url=url,
        status=status,
        headers={},
        body_text=json.dumps(payload),
        json_body=payload,
        error=UNKNOWN,
    )


def _transport(routes):
    def transport(method, url, body, headers):
        path = urlparse(url).path
        spec = routes.get((method, path))
        if spec is None:
            return HttpResult(ok=False, url=url, error="no_route")
        if callable(spec):
            return spec(method, url, body, headers)
        return spec

    return transport


def _unreachable_client(url: str) -> LoopbackClient:
    return LoopbackClient(
        transport=lambda *_args, **_kwargs: HttpResult(ok=False, url=url, error="unreachable")
    )


def test_loopback_client_rejects_cloud_and_writes():
    with pytest.raises(LoopbackHttpError):
        assert_loopback_url("https://ollama.com/api/tags")
    with pytest.raises(LoopbackHttpError):
        assert_loopback_url("http://localhost:11434/api/version")
    with pytest.raises(LoopbackHttpError):
        assert_allowed_path("POST", "/api/pull", {("GET", "/api/version")})
    client = LoopbackClient()
    with pytest.raises(LoopbackHttpError):
        client.request(
            "GET",
            "8.8.8.8",
            11434,
            "/api/version",
            allowed={("GET", "/api/version")},
        )


def test_thinking_not_inferred_from_model_name():
    record = thinking_from_show({"name": "deepseek-r1", "family": "deepseek"})
    assert record["capabilities"] is UNKNOWN
    assert record["thinking_listed_in_capabilities"] is UNKNOWN
    assert record["supported_thinking_values"] is UNKNOWN
    assert record["default_thinking"] is UNKNOWN


def test_thinking_recorded_only_when_show_supplies_fields():
    record = thinking_from_show(
        {
            "capabilities": ["completion", "thinking"],
            "supported_thinking_values": ["low", "medium", "high"],
            "default_thinking": "medium",
        }
    )
    assert record["thinking_listed_in_capabilities"] is True
    assert record["supported_thinking_values"] == ["low", "medium", "high"]
    assert record["default_thinking"] == "medium"
    absent_list = thinking_from_show({"capabilities": ["completion", "tools"]})
    assert absent_list["thinking_listed_in_capabilities"] is False
    assert absent_list["supported_thinking_values"] is UNKNOWN


def test_ollama_probe_records_show_and_never_pulls():
    pulled = {"called": False}

    def show(method, url, body, headers):
        payload = json.loads(body.decode("utf-8"))
        assert payload["model"] == "local-model"
        return _result(
            url,
            {
                "capabilities": ["completion"],
                "details": {"family": "unknown"},
            },
        )

    def pull(*_args, **_kwargs):
        pulled["called"] = True
        raise AssertionError("pull is forbidden")

    client = LoopbackClient(
        transport=_transport(
            {
                ("GET", "/api/version"): _result(
                    "http://127.0.0.1:11434/api/version", {"version": "0.12.0"}
                ),
                ("GET", "/api/tags"): _result(
                    "http://127.0.0.1:11434/api/tags",
                    {"models": [{"name": "local-model", "digest": "abc"}]},
                ),
                ("POST", "/api/show"): show,
                ("POST", "/api/pull"): pull,
            }
        )
    )
    result = probe_ollama(client=client)
    assert result["verdict"] == "pass"
    assert result["ollama_version"] == "0.12.0"
    assert result["downloads_attempted"] is False
    assert result["models"][0]["thinking"]["thinking_listed_in_capabilities"] is False
    assert result["models"][0]["thinking"]["supported_thinking_values"] is UNKNOWN
    assert pulled["called"] is False


def test_ollama_probe_fail_closed_when_unreachable():
    result = probe_ollama(client=_unreachable_client("http://127.0.0.1:11434/api/version"))
    assert result["verdict"] == "fail"
    assert result["ollama_version"] is UNKNOWN
    assert result["cloud_calls_attempted"] is False


def test_ollama_probe_rejects_non_loopback_without_io():
    def transport(*_args, **_kwargs):
        raise AssertionError("non-loopback must not touch the network")

    result = probe_ollama(host="ollama.com", client=LoopbackClient(transport=transport))
    assert result["verdict"] == "fail"
    assert result["ollama_version"] is UNKNOWN


def test_n8n_prerelease_fail_closed_unless_allowlisted():
    blocked = evaluate_n8n_safety("2.41.0-beta.1", allowlist=set())
    assert blocked["verdict"] == "fail"
    assert blocked["prerelease"] is True
    allowed = evaluate_n8n_safety("2.41.0-beta.1", allowlist={"2.41.0-beta.1"})
    assert allowed["verdict"] != "fail"
    assert allowed["prerelease_allowlisted"] is True
    assert allowed["agents_owner_review"] is True


def test_n8n_241_and_upgrade_candidate():
    flagged = evaluate_n8n_safety("2.41.3")
    assert flagged["verdict"] == "owner_review"
    assert flagged["agents_owner_review"] is True
    assert "n8n_2_41_default_enabled_agents" in flagged["flags"]
    older = evaluate_n8n_safety("2.39.0")
    assert older["upgrade_candidate"] == N8N_MIN_STABLE_LABEL
    assert older["verdict"] == "owner_review"
    assert older["flags"].count("upgrade_candidate_only") == 1
    current = evaluate_n8n_safety("2.40.5")
    assert current["verdict"] == "pass"
    assert current["upgrade_candidate"] is UNKNOWN


def test_n8n_probe_unreachable_is_fail_closed(tmp_path):
    result = probe_n8n(
        client=_unreachable_client("http://127.0.0.1:5678/healthz"),
        environ={"N8N_VERSION": "2.40.5", "N8N_ENCRYPTION_KEY": "must-not-appear"},
        allowlist_path=tmp_path / "missing.json",
    )
    assert result["verdict"] == "fail"
    assert "n8n_loopback_unreachable" in result["errors"]
    assert result["observable_env"]["N8N_VERSION"] == "2.40.5"
    assert "N8N_ENCRYPTION_KEY" not in result["observable_env"]
    assert result["config_edited"] is False
    assert result["upgrade_attempted"] is False


def test_n8n_probe_records_observable_settings_only():
    settings = {
        "versionCli": "2.41.0",
        "instanceAi": {"enabled": True, "apiKey": "sk-secret-must-redact"},
    }
    client = LoopbackClient(
        transport=_transport(
            {
                ("GET", "/healthz"): _result("http://127.0.0.1:5678/healthz", {"status": "ok"}),
                ("GET", "/healthz/readiness"): _result(
                    "http://127.0.0.1:5678/healthz/readiness", {"status": "ok"}
                ),
                ("GET", "/rest/settings"): _result(
                    "http://127.0.0.1:5678/rest/settings", settings
                ),
            }
        )
    )
    result = probe_n8n(client=client, environ={})
    assert result["n8n_version"] == "2.41.0"
    assert result["verdict"] == "owner_review"
    assert result["agent_related"]["instanceAi"]["enabled"] is True
    dumped = json.dumps(result)
    assert "sk-secret-must-redact" not in dumped
    assert "REDACTED" in dumped


def test_bench_spec_pins_candidates_and_required_fields():
    spec = load_bench_spec()
    validate_bench_spec(spec, spec_path=REPO_ROOT / "rd/manifests/parser_bench_spec.v1.json")
    assert spec["candidates"][1]["version"] == DOCLING_PINNED_VERSION
    assert spec["candidates"][2]["version"] == MINERU_PINNED_VERSION
    assert spec["candidates"][2]["license_accepted"] is False
    assert spec["candidates"][2]["enabled"] is False
    fixture = REPO_ROOT / spec["test_sources"][0]["path"]
    assert sha256_file(fixture) == spec["test_sources"][0]["input_sha256"]


def test_mineru_stays_blocked_without_license(tmp_path):
    spec = load_bench_spec()
    result = run_parser_bench(
        spec=spec,
        output_root=tmp_path / "bench",
        allowed_roots=[tmp_path],
        mode="spec_only",
        environ={"DATABOSSX_RD_MINERU_LICENSE_ACCEPTED": "false"},
    )
    mineru = next(item for item in result["candidates"] if item["id"] == "mineru")
    docling = next(item for item in result["candidates"] if item["id"] == "docling")
    assert mineru["blocked"] is True
    assert mineru["block_reason"] == "LICENSE_ACCEPTED=false"
    assert mineru["ran"] is False
    assert docling["ran"] is False
    assert result["installs_attempted"] is False
    assert (tmp_path / "bench" / "run.json").exists()


def test_current_pipeline_bench_hashes_and_detects_drops(tmp_path):
    spec = load_bench_spec()
    result = run_parser_bench(
        spec=spec,
        output_root=tmp_path / "bench-current",
        allowed_roots=[tmp_path],
        mode="current_only",
        environ={},
    )
    assert result["verdict"] == "pass"
    source = result["sources"][0]
    assert source["input_sha256"] == spec["test_sources"][0]["input_sha256"]
    assert source["source_page_count"] == 2
    assert source["extracted_page_count"] == 2
    assert source["missing_or_dropped_pages"] == []
    assert source["output_sha256"] != UNKNOWN
    assert source["page_provenance"][0]["source_sha256"] == source["input_sha256"]
    assert source["extracted_table_count"] is UNKNOWN

    def drop_page_two(path: Path):
        text = path.read_text(encoding="utf-8")
        return text.replace("[PAGE 2]", "").replace(
            "Additional fictional paragraph for provenance and drop-detection checks.",
            "",
        ), "read-text", False, ""

    dropped = measure_extractor(
        REPO_ROOT / spec["test_sources"][0]["path"],
        drop_page_two,
        deterministic_expected=True,
    )
    assert dropped["missing_or_dropped_pages"] == [2]


def test_missing_drop_evidence_fails_closed(tmp_path):
    spec = load_bench_spec()

    def unmarked(_path: Path):
        return "no page markers", "read-text", False, ""

    result = run_parser_bench(
        spec=spec,
        output_root=tmp_path / "bench-unknown",
        allowed_roots=[tmp_path],
        mode="current_only",
        current_extractor=unmarked,
        environ={},
    )
    assert result["verdict"] == "fail"
    assert "drop_detection_unknown" in result["sources"][0]["errors"]
    assert result["sources"][0]["missing_or_dropped_pages"] is UNKNOWN


def test_single_writer_and_forbidden_production_paths(tmp_path):
    target = tmp_path / "rd-out"
    with exclusive_writer(target, "writer-a", [tmp_path]) as first:
        first.write_json("a.json", {"ok": True})
        with pytest.raises(WriterConflict):
            exclusive_writer(target, "writer-b", [tmp_path]).__enter__()
    forbidden = (
        (REPO_ROOT / "output" / "leaked", REPO_ROOT / "output"),
        (REPO_ROOT / "website" / "rd", REPO_ROOT / "website"),
    )
    for path, root in forbidden:
        with pytest.raises(IsolationError):
            with exclusive_writer(path, "writer-a", [root]):
                pass


def test_live_loopback_observation_records_unknown_when_absent():
    ollama = probe_ollama()
    n8n = probe_n8n(environ={})
    if ollama["verdict"] == "pass":
        assert ollama["ollama_version"] is not UNKNOWN
        for model in ollama["models"]:
            thinking = model["thinking"]
            if thinking["supported_thinking_values"] is not UNKNOWN:
                assert isinstance(thinking["supported_thinking_values"], list)
    else:
        assert ollama["ollama_version"] is UNKNOWN
        assert ollama["verdict"] == "fail"
    if n8n["verdict"] != "fail":
        assert n8n["n8n_version"] is not UNKNOWN
    else:
        assert n8n["n8n_version"] is UNKNOWN or "n8n_loopback_unreachable" in n8n["errors"]
    assert ollama["cloud_calls_attempted"] is False
    assert n8n["cloud_calls_attempted"] is False
    assert n8n["config_edited"] is False
