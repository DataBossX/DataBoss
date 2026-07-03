import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workflows.runner import Workflow  # noqa: E402


class TestWorkflow(unittest.TestCase):
    def test_steps_run_in_order_and_share_context(self):
        wf = Workflow("demo")
        wf.step("one", lambda ctx: 1).step("two", lambda ctx: ctx["one"] + 1)
        res = wf.run()
        self.assertTrue(res.ok)
        self.assertEqual([r.name for r in res.results], ["one", "two"])
        self.assertEqual(res.results[1].value, 2)

    def test_halts_on_failure(self):
        wf = Workflow("boom")

        def explode(ctx):
            raise ValueError("kaboom")

        wf.step("ok", lambda ctx: "fine").step("bad", explode).step("never", lambda ctx: "unreached")
        res = wf.run()
        self.assertFalse(res.ok)
        # Third step should not have executed.
        self.assertEqual(len(res.results), 2)
        self.assertIn("kaboom", res.results[1].error)


if __name__ == "__main__":
    unittest.main()
