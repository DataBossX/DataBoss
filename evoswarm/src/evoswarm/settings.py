"""Typed settings via pydantic-settings — env-driven, strict, 12-factor."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EVOSWARM_", env_file=".env", extra="ignore")

    # LLM routing — defaults to the most capable current Claude model.
    default_model: str = "claude-opus-4-8"
    fast_model: str = "claude-haiku-4-5-20251001"
    anthropic_api_key: str = Field(default="", repr=False)

    # Infra
    postgres_dsn: str = "postgresql://evoswarm:evoswarm@localhost:5432/evoswarm"
    neo4j_uri: str = "bolt://localhost:7687"
    redis_url: str = "redis://localhost:6379/0"
    temporal_host: str = "localhost:7233"

    # Oklahoma county records (reuses DataBoss OKCountyClient conventions)
    okcounty_api_base_url: str = "https://api.okcountyrecords.com/v1"
    okcounty_api_key: str = Field(default="", repr=False)
    okcounty_cost_per_image: float = 0.50
    okcounty_cost_per_search: float = 0.10

    # EvoLoop guardrails
    evoloop_enabled: bool = False
    evoloop_min_eval_score: float = 0.85
    evoloop_require_human_pr: bool = True


settings = Settings()
