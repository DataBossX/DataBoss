from pathlib import Path

from scripts import scan_secrets


def test_scanner_ignores_env_lookups_and_empty_templates(tmp_path, monkeypatch):
    source = tmp_path / "settings.py"
    source.write_text(
        'OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")\n'
        'template = """OPENAI_API_KEY=\nOPENAI_MODEL=gpt"""\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(scan_secrets, "tracked_files", lambda: [source])
    assert scan_secrets.scan() == []


def test_scanner_rejects_literal_credentials(tmp_path, monkeypatch):
    source = tmp_path / "unsafe.env"
    source.write_text("SERVICE_API_KEY=super-secret-real-value\n", encoding="utf-8")
    monkeypatch.setattr(scan_secrets, "tracked_files", lambda: [source])
    assert scan_secrets.scan() == [f"{source}:1: credential assignment"]


def test_env_example_placeholders_pass(tmp_path, monkeypatch):
    source = tmp_path / ".env.example"
    source.write_text(
        "SERVICE_API_KEY=your_api_key_here\nOPENAI_API_KEY=sk-...\nEMPTY_TOKEN=\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(scan_secrets, "tracked_files", lambda: [Path(source)])
    assert scan_secrets.scan() == []


def test_env_example_is_not_blanket_ignored(tmp_path, monkeypatch):
    # A real credential committed into an example template MUST still be caught.
    source = tmp_path / ".env.example"
    source.write_text(
        "SERVICE_API_KEY=A1b2C3d4E5f6G7h8realvalue\n", encoding="utf-8"
    )
    monkeypatch.setattr(scan_secrets, "tracked_files", lambda: [Path(source)])
    assert scan_secrets.scan() == [f"{source}:1: credential assignment"]
