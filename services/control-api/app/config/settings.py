"""Twelve-factor configuration loaded from the environment."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-insecure-change-me"  # noqa: S105


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


class ExecutionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONDUCTOR_EXEC_", extra="ignore")

    engine: str = "local"
    max_concurrency: int = 8


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
