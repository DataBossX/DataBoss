"""The Streamlit dashboard module imports cleanly (no import-time side effects
that require a running Streamlit server)."""


def test_dashboard_imports():
    import importlib
    mod = importlib.import_module("app.dashboard")
    assert hasattr(mod, "main")


def test_run_agent_cli_imports():
    import importlib
    mod = importlib.import_module("tools.run_agent")
    assert hasattr(mod, "main")


def test_healthcheck_imports_and_runs():
    import importlib
    hc = importlib.import_module("tools.healthcheck")
    critical, advisory = hc.run_healthcheck()
    assert any("Python" in c[0] for c in critical)
