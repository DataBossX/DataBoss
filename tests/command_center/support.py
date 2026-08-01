"""Shared fixtures for Command Center tests."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVICE_ROOT = os.path.join(REPO_ROOT, "services", "control_api")
if SERVICE_ROOT not in sys.path:
    sys.path.insert(0, SERVICE_ROOT)

from command_center.kernel import Actor, ControlKernel  # noqa: E402
from command_center.runner import LocalRunner, RunnerConfig  # noqa: E402

OWNER = Actor("ryan", "OWNER", session_id="s1", device_id="d1", stepped_up=True)
OPERATOR = Actor("op", "OPERATOR", session_id="s2", device_id="d2")
REVIEWER = Actor("rev", "REVIEWER", session_id="s3", device_id="d3")
VIEWER = Actor("viewer", "VIEWER", session_id="s4", device_id="d4")
WATCHER = Actor("watcher:security", "REVIEWER", session_id="s5", device_id="d5")


#: Set to a ``postgres://`` DSN to run the whole suite against real PostgreSQL.
#: Unset, the suite runs on SQLite. Both must pass -- see ADR-0003.
POSTGRES_DSN = os.environ.get("DBX_CC_TEST_DSN", "").strip()


def _new_schema_name() -> str:
    import secrets

    return f"cc_{secrets.token_hex(8)}"


class KernelTestCase(unittest.TestCase):
    """Gives each test a private database and work root.

    On SQLite that is a fresh file. On PostgreSQL it is a fresh schema pinned
    via ``search_path``, which gives the same isolation without needing a
    database per test.
    """

    def setUp(self):
        self.workdir = tempfile.mkdtemp(prefix="dbx-cc-test-")
        if POSTGRES_DSN:
            self.db_path = self._make_pg_schema()
        else:
            self.db_path = os.path.join(self.workdir, "cc.db")
        self.kernel = ControlKernel.open(self.db_path)
        for actor, name in ((OWNER, "Ryan"), (OPERATOR, "Operator"),
                            (REVIEWER, "Reviewer"), (VIEWER, "Viewer")):
            self.kernel.upsert_user(actor.user_id, name, actor.role)
        self.kernel.upsert_user(WATCHER.user_id, "Security Watcher", "REVIEWER")
        self.addCleanup(shutil.rmtree, self.workdir, True)
        self.addCleanup(self.kernel.conn.close)

    def _make_pg_schema(self) -> str:
        """Create a throwaway schema and return a DSN pinned to it."""
        from command_center import pg_wire

        schema = _new_schema_name()
        admin = pg_wire.connect(POSTGRES_DSN)
        try:
            admin.execute(f"CREATE SCHEMA {schema}")
        finally:
            admin.close()

        def drop():
            conn = pg_wire.connect(POSTGRES_DSN)
            try:
                conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            finally:
                conn.close()

        self.addCleanup(drop)
        separator = "&" if "?" in POSTGRES_DSN else "?"
        return f"{POSTGRES_DSN}{separator}schema={schema}"

    def new_kernel(self) -> ControlKernel:
        """A second, independent connection to the same database.

        Concurrency tests use this so races are decided by SQLite constraints
        rather than by a Python-level lock.
        """
        kernel = ControlKernel(__import__("command_center.db", fromlist=["db"]).connect(self.db_path))
        self.addCleanup(kernel.conn.close)
        return kernel

    def runner(self, *, simulation_only: bool = True) -> LocalRunner:
        return LocalRunner(
            self.kernel,
            RunnerConfig(workroot=os.path.join(self.workdir, "runner"),
                         simulation_only=simulation_only),
        )

    def make_command(self, *, key: str = "k1", operation: str = "title.simulate_interest_rollup",
                     project: str = "synthetic-alpha", actor: Actor = OWNER) -> dict:
        return self.kernel.create_command(
            actor,
            idempotency_key=key,
            transcript_text="run the interest roll up for project synthetic-alpha",
            intent={
                "goal": "roll up interests", "operation": operation,
                "target_project": project, "target_resource": f"project.{project}",
                "parameters": {"project_id": project}, "unresolved": [],
            },
            confirmed=True,
        )

    def issue_task(self, *, adapter: str = "title.simulate_interest_rollup",
                   scope: str = "project.synthetic-alpha", mode: str = "SIMULATED",
                   risk: str = "SIMULATION", actor: Actor = OWNER,
                   parameters=None, approval_token_id=None, input_hashes=None,
                   lease=None, key: str = "k1") -> dict:
        command = self.make_command(key=key, actor=actor)
        lease = lease or self.kernel.claim_lease(actor, scope)
        envelope = self.kernel.build_task_envelope(
            command_id=command["command_id"], resource_scope=scope, adapter=adapter,
            parameters=parameters if parameters is not None else {"project_id": "synthetic-alpha"},
            execution_mode=mode, risk_class=risk, lease=lease,
            approval_token_id=approval_token_id, input_hashes=input_hashes,
        )
        persisted = self.kernel.persist_task_envelope(envelope, actor)
        self.kernel.set_job_state(persisted["job_id"], "QUEUED")
        self.kernel.set_job_state(persisted["job_id"], "APPROVED")
        return {"command": command, "lease": lease, "envelope": envelope,
                "job_id": persisted["job_id"]}
