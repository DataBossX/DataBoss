"""Unit tests for the LLM layer: availability, retry, timeout, degradation."""

import asyncio

import pytest

import config
import llm


def test_no_providers_when_keys_absent():
    # conftest clears provider keys, so nothing should be available.
    assert llm.available_models() == []
    assert all(v == "unavailable" for v in llm.provider_status().values())


def test_analyze_success(monkeypatch):
    monkeypatch.setattr(llm, "_call_sync", lambda model, prompt: "SUMMARY")
    result = asyncio.run(llm.analyze("some text", "claude", "general_summary"))
    assert result["analysis"] == "SUMMARY"
    assert result["model_used"] == "claude"
    assert result["attempts"] == 1


def test_analyze_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(config, "LLM_MAX_RETRIES", 2)

    async def _noop(*_a, **_k):
        return None

    monkeypatch.setattr(llm.asyncio, "sleep", _noop)

    calls = {"n": 0}

    def flaky(model, prompt):
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient")
        return "OK"

    monkeypatch.setattr(llm, "_call_sync", flaky)
    result = asyncio.run(llm.analyze("t", "gpt-4", "general_summary"))
    assert result["analysis"] == "OK"
    assert result["attempts"] == 2


def test_analyze_gives_up_and_raises(monkeypatch):
    monkeypatch.setattr(config, "LLM_MAX_RETRIES", 0)

    def always_fail(model, prompt):
        raise RuntimeError("provider down")

    monkeypatch.setattr(llm, "_call_sync", always_fail)
    with pytest.raises(llm.LLMError):
        asyncio.run(llm.analyze("t", "claude", "general_summary"))


def test_analyze_times_out(monkeypatch):
    import time

    monkeypatch.setattr(config, "LLM_MAX_RETRIES", 0)
    monkeypatch.setattr(config, "LLM_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(llm, "_call_sync", lambda m, p: time.sleep(0.5) or "late")
    with pytest.raises(llm.LLMError):
        asyncio.run(llm.analyze("t", "claude", "general_summary"))
