import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Config, load_config  # noqa: E402


class TestConfig(unittest.TestCase):
    def test_loads_settings_toml(self):
        cfg = load_config()
        # settings.toml ships with an [llms] section in this repo.
        self.assertIsInstance(cfg.settings, dict)
        self.assertIsNotNone(cfg.get("execution", "max_concurrent", default=None))

    def test_nested_get_default(self):
        cfg = Config(settings={"a": {"b": 1}})
        self.assertEqual(cfg.get("a", "b"), 1)
        self.assertIsNone(cfg.get("a", "missing"))
        self.assertEqual(cfg.get("nope", default="d"), "d")

    def test_redact_never_reveals(self):
        self.assertEqual(Config.redact(None), "<unset>")
        red = Config.redact("sk_supersecretvalue")
        self.assertTrue(red.startswith("sk_"))
        self.assertNotIn("supersecret", red)

    def test_secret_status_reports_presence_only(self):
        os.environ["OPENAI_API_KEY"] = "sk_test_value"
        try:
            cfg = Config()
            status = cfg.secret_status()
            self.assertTrue(status["OPENAI_API_KEY"])
            # The value itself is never exposed by the status map.
            self.assertNotIn("sk_test_value", str(status))
        finally:
            del os.environ["OPENAI_API_KEY"]


if __name__ == "__main__":
    unittest.main()
