from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KernelConfig:
    repo_root: Path
    runtime_root: Path
    database_path: Path
    vault_root: Path
    projects_root: Path
    migrations_root: Path
    max_file_bytes: int = 512 * 1024 * 1024

    @classmethod
    def default(cls, runtime_root: Path | None = None) -> "KernelConfig":
        repo = Path(__file__).resolve().parents[2]
        runtime = (runtime_root or repo / "runtime").resolve()
        return cls(
            repo_root=repo,
            runtime_root=runtime,
            database_path=runtime / "kernel.sqlite3",
            vault_root=runtime / "vault",
            projects_root=runtime / "projects",
            migrations_root=repo / "migrations",
        )

    def initialize_directories(self) -> None:
        for path in (self.runtime_root, self.vault_root, self.projects_root):
            path.mkdir(parents=True, exist_ok=True)
