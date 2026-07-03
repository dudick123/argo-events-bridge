"""Application configuration loaded from environment variables.

All variables are documented in docs/config-reference.md. Secrets (API keys,
credentials) are injected by ESO from Azure Key Vault in-cluster; locally they
come from a .env file.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AkuitySettings(BaseSettings):
    """Akuity API connection and rate-limit settings."""

    model_config = SettingsConfigDict(env_prefix="AKUITY_", env_file=".env", extra="ignore")

    base_url: str
    org_id: str
    instance_id: str
    api_key: str
    app_label_selector: str = "env=prod"
    min_request_interval_ms: int = Field(default=1000, ge=0)
    max_retries: int = Field(default=3, ge=0)


class SnowSettings(BaseSettings):
    """ServiceNow CR API connection and retry settings."""

    model_config = SettingsConfigDict(env_prefix="SNOW_", env_file=".env", extra="ignore")

    base_url: str
    api_key: str
    max_retries: int = Field(default=3, ge=0)
    retry_backoff_base_ms: int = Field(default=2000, ge=0)
    timeout_seconds: float = Field(default=30.0, gt=0)


class RedisSettings(BaseSettings):
    """Redis connection settings for durable bridge state."""

    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")

    url: str = "redis://localhost:6379/0"
    key_ttl_seconds: int = Field(default=86400, gt=0)


class ObservabilitySettings(BaseSettings):
    """Logging and Datadog settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"
    datadog_statsd_host: str = "localhost"
    datadog_statsd_port: int = 8125
    service_name: str = "change-bridge"
    env: str = "prod"


class Settings(BaseSettings):
    """Top-level bridge settings aggregating all sections."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    poll_interval_seconds: float = Field(default=15.0, gt=0)
    stabilization_window_seconds: float = Field(default=300.0, ge=0)

    akuity: AkuitySettings = Field(default_factory=AkuitySettings)  # type: ignore[arg-type]
    snow: SnowSettings = Field(default_factory=SnowSettings)  # type: ignore[arg-type]
    redis: RedisSettings = Field(default_factory=RedisSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)


def load_settings() -> Settings:
    """Load settings from the environment (and .env when present)."""
    return Settings()
