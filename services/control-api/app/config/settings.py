"""Twelve-factor configuration loaded from the environment."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
