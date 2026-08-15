"""Twelve-factor configuration loaded from the environment."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-insecure-change-me-not-for-production-use"  # noqa: S105


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONDUCTOR_DB_", extra="ignore")

    url: str = "postgresql+asyncpg://conductor:conductor@localhost:5432/conductor"
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout_seconds: int = 30
    pool_recycle_seconds: int = 1800
    echo: bool = False


class ObservabilitySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONDUCTOR_OTEL_", extra="ignore")

    service_name: str = "conductor-control-api"
    otlp_endpoint: str | None = None
    traces_enabled: bool = True


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONDUCTOR_AUTH_", extra="ignore")

    secret: str = _DEV_SECRET
    issuer: str = "conductor"
    audience: str = "conductor-api"
    algorithm: str = "HS256"
    access_ttl_seconds: int = 900
    refresh_ttl_seconds: int = 1209600


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONDUCTOR_LLM_", extra="ignore")

    provider: str = "fake"  # "fake" or "http"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "conductor-default"
    timeout_seconds: int = 30


class TemporalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONDUCTOR_TEMPORAL_", extra="ignore")

    host: str = "localhost:7233"
    namespace: str = "default"
    task_queue: str = "conductor-runs"
    workflow_execution_timeout_seconds: int = 300
    activity_start_to_close_timeout_seconds: int = 60
    activity_max_attempts: int = 1


class ExecutionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONDUCTOR_EXEC_", extra="ignore")

    engine: str = "local"
    max_concurrency: int = 8


class PolicySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONDUCTOR_POLICY_", extra="ignore")

    engine: str = "local"  # "local" or "opa"
    opa_url: str = "http://localhost:8181"
    opa_decision_path: str = "v1/data/conductor/decision"
    opa_timeout_seconds: float = 5.0
    opa_fail_closed: bool = True
    require_approval_for_high_priority: bool = False
    require_approval_for_external_tools: bool = False
    denied_tool_kinds: list[str] = Field(default_factory=list)


class EventingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONDUCTOR_EVENTS_", extra="ignore")

    bus: str = "null"  # "null" or "kafka"
    kafka_bootstrap_servers: str = "localhost:9092"
    topic: str = "conductor.run-events"
    relay_batch_size: int = 100
    relay_poll_interval_seconds: float = 1.0


class CostSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONDUCTOR_COST_", extra="ignore")

    prompt_usd_per_1k: float = 0.00015
    completion_usd_per_1k: float = 0.0006


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONDUCTOR_", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    default_page_size: int = 20
    max_page_size: int = 100
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    temporal: TemporalSettings = Field(default_factory=TemporalSettings)
    policy: PolicySettings = Field(default_factory=PolicySettings)
    events: EventingSettings = Field(default_factory=EventingSettings)
    cost: CostSettings = Field(default_factory=CostSettings)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @model_validator(mode="after")
    def _reject_default_secret_in_production(self) -> AppSettings:
        if self.is_production and self.auth.secret == _DEV_SECRET:
            raise ValueError("CONDUCTOR_AUTH_SECRET must be set in production")
        return self


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
