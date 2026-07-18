from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataBossConfig:
    """Filesystem layout for the canonical local-first runtime."""

    repo_root: Path
    runtime_dirname: str = "runtime"

    @classmethod
    def from_repo_root(cls, repo_root: str | Path) -> "DataBossConfig":
        return cls(repo_root=Path(repo_root).resolve())

    @property
    def runtime_root(self) -> Path:
        return self.repo_root / self.runtime_dirname

    @property
    def projects_root(self) -> Path:
        return self.runtime_root / "projects"

    def project_root(self, project_id: str) -> Path:
        return self.projects_root / project_id

    def project_db_path(self, project_id: str) -> Path:
        return self.project_root(project_id) / "project.db"

    def project_vault_root(self, project_id: str) -> Path:
        return self.project_root(project_id) / "vault" / "sha256"

    def project_artifacts_root(self, project_id: str) -> Path:
        return self.project_root(project_id) / "artifacts"

    def project_exports_root(self, project_id: str) -> Path:
        return self.project_root(project_id) / "exports"

    def project_logs_root(self, project_id: str) -> Path:
        return self.project_root(project_id) / "logs"

    def project_snapshots_root(self, project_id: str) -> Path:
        return self.project_root(project_id) / "snapshots"

    def project_review_root(self, project_id: str) -> Path:
        return self.project_root(project_id) / "review"

    def ensure_runtime_dirs(self, project_id: str) -> None:
        for path in (
            self.projects_root,
            self.project_root(project_id),
            self.project_vault_root(project_id),
            self.project_artifacts_root(project_id),
            self.project_exports_root(project_id),
            self.project_logs_root(project_id),
            self.project_snapshots_root(project_id),
            self.project_review_root(project_id),
        ):
            path.mkdir(parents=True, exist_ok=True)
