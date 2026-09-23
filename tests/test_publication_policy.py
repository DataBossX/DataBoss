from __future__ import annotations

from databossx.governor.policy_gate import scan_publication_policy


def test_gate_fails_on_synthetic_secret(tmp_path):
    secret = "sk-" + ("a" * 24)
    (tmp_path / "leak.py").write_text(f'API_KEY = "{secret}"\n', encoding="utf-8")
    result = scan_publication_policy(tmp_path)
    assert result["status"] == "FAIL"
    assert result["findings"][0]["kind"] == "credential"


def test_gate_allows_clean_tree(tmp_path):
    (tmp_path / "ok.py").write_text("VALUE = 1\n", encoding="utf-8")
    result = scan_publication_policy(tmp_path)
    assert result["status"] == "PASS"
    assert result["scanned"] >= 1


def test_current_repo_gate_documents_status():
    result = scan_publication_policy(".")
    assert "scanned" in result
    assert result["scanned"] > 20
    # Architecture docs are allowlisted; a FAIL here is a new leak, not history.
    assert result["status"] == "PASS", result["findings"]
