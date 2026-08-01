"""Project-context retriever.

Answers "what is actually happening right now" from the database rather than
from conversation history. Every fact returned carries a source and an
``observed_at`` timestamp so nothing stale is presented as current truth.

Artifacts are addressed by stable ID. The locator column is read here and never
returned: callers get ``label``, ``artifact_class``, ``sha256``, and size.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import CommandBrainError
from .hashing_bridge import hash_registered_artifact
from .util import Clock


class ArtifactNotRegistered(CommandBrainError):
    code = "ARTIFACT_NOT_REGISTERED"


@dataclass(frozen=True)
class Fact:
    statement: str
    source: str
    observed_at: str

    def to_dict(self) -> dict:
        return {"statement": self.statement, "source": self.source, "observed_at": self.observed_at}


class StateRetriever:
    def __init__(self, store, clock: Clock | None = None):
        self.store = store
        self.clock = clock or store.clock

    # -- registration -----------------------------------------------------
    def register_artifact(
        self,
        artifact_id: str,
        artifact_class: str,
        label: str,
        sha256: str,
        *,
        locator: str = "",
        byte_size: int = 0,
        project_id: str | None = None,
        synthetic: bool = True,
    ) -> str:
        self.store.execute(
            """
            INSERT OR REPLACE INTO cb_artifacts (
                artifact_id, project_id, artifact_class, label, sha256, byte_size,
                locator, synthetic, quarantined, registered_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                artifact_id,
                project_id,
                artifact_class,
                label,
                sha256,
                byte_size,
                locator,
                int(synthetic),
                self.store.now(),
            ),
        )
        self.store.audit(
            "artifact.registered",
            "artifact",
            artifact_id,
            {"artifact_class": artifact_class, "label": label, "sha256": sha256, "synthetic": synthetic},
            project_id=project_id,
        )
        return artifact_id

    def artifact_row(self, artifact_id: str):
        row = self.store.fetchone(
            "SELECT * FROM cb_artifacts WHERE artifact_id = ?", (artifact_id,)
        )
        if row is None:
            raise ArtifactNotRegistered(
                f"{artifact_id!r} is not a registered artifact. "
                "The Command Brain only reads artifacts registered by ID.",
                detail={"artifact_id": artifact_id},
            )
        return row

    # -- reads ------------------------------------------------------------
    def artifact_metadata(self, artifact_id: str) -> dict:
        """Metadata only. Never includes the locator."""
        row = self.artifact_row(artifact_id)
        return {
            "artifact_id": row["artifact_id"],
            "project_id": row["project_id"],
            "artifact_class": row["artifact_class"],
            "label": row["label"],
            "sha256": row["sha256"],
            "byte_size": row["byte_size"],
            "synthetic": bool(row["synthetic"]),
            "quarantined": bool(row["quarantined"]),
            "registered_at": row["registered_at"],
        }

    def artifact_hash(self, artifact_id: str) -> str:
        return self.artifact_row(artifact_id)["sha256"]

    def verify_artifact_hash(self, artifact_id: str) -> dict:
        """Recompute the hash from the server-resolved locator, if reachable."""
        row = self.artifact_row(artifact_id)
        recorded = row["sha256"]
        observed = hash_registered_artifact(row["locator"])
        if observed is None:
            return {
                "artifact_id": artifact_id,
                "recorded_sha256": recorded,
                "verified": False,
                "state": "NOT_VERIFIED",
                "detail": "Artifact bytes are not reachable from this runtime; hash not recomputed.",
            }
        return {
            "artifact_id": artifact_id,
            "recorded_sha256": recorded,
            "observed_sha256": observed,
            "verified": observed == recorded,
            "state": "VERIFIED" if observed == recorded else "MISMATCH",
            "detail": "Recomputed from the registered source bytes.",
        }

    def projects(self) -> list[dict]:
        rows = self.store.fetchall(
            "SELECT id, name, jurisdiction_code, status, policy_version FROM projects ORDER BY id"
        )
        return [dict(row) for row in rows]

    def project_status(self, project_id: str) -> dict:
        row = self.store.fetchone(
            """
            SELECT p.id, p.name, p.jurisdiction_code, p.status, tp.release_state, tp.report_type
              FROM projects p LEFT JOIN title_projects tp ON tp.project_id = p.id
             WHERE p.id = ?
            """,
            (project_id,),
        )
        base = dict(row) if row else {"id": project_id, "name": project_id, "status": "UNKNOWN"}
        base.update(
            {
                "active_jobs": self.active_jobs(project_id),
                "open_defects": self.open_defects(project_id),
                "release_holds": self.release_holds(project_id),
                "artifacts": self.artifacts(project_id),
                "pending_approvals": self.pending_approvals(),
                "human_review_open": len(self.store.open_human_reviews(project_id)),
                "observed_at": self.clock.now_iso(),
            }
        )
        return base

    def artifacts(self, project_id: str | None = None) -> list[dict]:
        if project_id:
            rows = self.store.fetchall(
                "SELECT artifact_id FROM cb_artifacts WHERE project_id = ? ORDER BY artifact_id",
                (project_id,),
            )
        else:
            rows = self.store.fetchall("SELECT artifact_id FROM cb_artifacts ORDER BY artifact_id")
        return [self.artifact_metadata(row["artifact_id"]) for row in rows]

    def active_jobs(self, project_id: str | None = None) -> list[dict]:
        query = "SELECT * FROM cb_jobs WHERE state IN ('QUEUED', 'RUNNING')"
        params: tuple = ()
        if project_id:
            query += " AND project_id = ?"
            params = (project_id,)
        return [dict(row) for row in self.store.fetchall(query + " ORDER BY created_at", params)]

    def open_defects(self, project_id: str | None = None) -> list[dict]:
        query = "SELECT * FROM cb_defects WHERE state = 'OPEN'"
        params: tuple = ()
        if project_id:
            query += " AND project_id = ?"
            params = (project_id,)
        return [dict(row) for row in self.store.fetchall(query + " ORDER BY created_at", params)]

    def release_holds(self, project_id: str | None = None) -> list[dict]:
        query = "SELECT * FROM cb_holds WHERE active = 1"
        params: tuple = ()
        if project_id:
            query += " AND project_id = ?"
            params = (project_id,)
        return [dict(row) for row in self.store.fetchall(query + " ORDER BY created_at", params)]

    def pending_approvals(self) -> list[dict]:
        rows = self.store.fetchall(
            """
            SELECT envelope_id, project_id, envelope_hash, autonomy_level, created_at, expires_at
              FROM cb_task_envelopes WHERE state = 'DRAFT' ORDER BY created_at
            """
        )
        return [dict(row) for row in rows]

    def system_status(self, policy_profile=None, gateway=None) -> dict:
        jobs = self.active_jobs()
        status = {
            "observed_at": self.clock.now_iso(),
            "projects": len(self.projects()),
            "active_jobs": len(jobs),
            "queued_jobs": len([job for job in jobs if job["state"] == "QUEUED"]),
            "open_defects": len(self.open_defects()),
            "active_holds": len(self.release_holds()),
            "pending_approvals": len(self.pending_approvals()),
            "open_human_reviews": len(self.store.open_human_reviews()),
            "ledger": self.store.verify_ledger(),
        }
        if policy_profile is not None:
            status["policy"] = policy_profile.to_dict()
        if gateway is not None:
            status["models"] = {
                "verified": gateway.verified_models(),
                "unverified": gateway.unverified_models(),
            }
        return status

    # -- narrative --------------------------------------------------------
    def blockers(self, project_id: str) -> list[Fact]:
        """Why the project cannot move, each with a source and a timestamp."""
        facts: list[Fact] = []
        observed_at = self.clock.now_iso()
        for hold in self.release_holds(project_id):
            facts.append(
                Fact(
                    f"Release hold {hold['hold_id']} ({hold['scope']}) is active: {hold['reason']}.",
                    f"cb_holds:{hold['hold_id']}",
                    hold["created_at"],
                )
            )
        for defect in self.open_defects(project_id):
            facts.append(
                Fact(
                    f"Open {defect['severity']} defect {defect['defect_id']}: {defect['summary']}.",
                    f"cb_defects:{defect['defect_id']}",
                    defect["created_at"],
                )
            )
        for item in self.store.open_human_reviews(project_id):
            facts.append(
                Fact(
                    f"Awaiting human review: {item['question']}",
                    f"cb_human_review_queue:{item['item_id']}",
                    item["created_at"],
                )
            )
        for approval in self.pending_approvals():
            if approval["project_id"] == project_id:
                facts.append(
                    Fact(
                        f"TaskEnvelope {approval['envelope_id']} is drafted and awaiting your approval.",
                        f"cb_task_envelopes:{approval['envelope_id']}",
                        approval["created_at"],
                    )
                )
        if not facts:
            facts.append(
                Fact(
                    "No active hold, open defect, queued review, or pending approval was found.",
                    "cb_holds/cb_defects/cb_human_review_queue/cb_task_envelopes",
                    observed_at,
                )
            )
        return facts

    def status_facts(self, project_id: str) -> list[Fact]:
        status = self.project_status(project_id)
        observed_at = status["observed_at"]
        facts = [
            Fact(
                f"Project {status.get('name', project_id)} is in state "
                f"{status.get('status', 'UNKNOWN')} (release state "
                f"{status.get('release_state', 'UNKNOWN')}).",
                "projects/title_projects",
                observed_at,
            ),
            Fact(
                f"{len(status['active_jobs'])} job(s) active, {len(status['open_defects'])} open defect(s), "
                f"{len(status['release_holds'])} active hold(s).",
                "cb_jobs/cb_defects/cb_holds",
                observed_at,
            ),
            Fact(
                f"{len(status['pending_approvals'])} TaskEnvelope draft(s) awaiting approval; "
                f"{status['human_review_open']} item(s) in the human-review queue.",
                "cb_task_envelopes/cb_human_review_queue",
                observed_at,
            ),
        ]
        for artifact in status["artifacts"][:8]:
            facts.append(
                Fact(
                    f"Controlling artifact {artifact['artifact_id']} "
                    f"({artifact['artifact_class']}, sha256 {artifact['sha256'][:12]}…)"
                    + (" [SYNTHETIC]" if artifact["synthetic"] else ""),
                    f"cb_artifacts:{artifact['artifact_id']}",
                    artifact["registered_at"],
                )
            )
        return facts
