"""Unit tests for environment-driven configuration."""

import pytest

from bridge.config import Settings

REQUIRED_ENV = {
    "AKUITY_BASE_URL": "https://akuity.example.com",
    "AKUITY_ORG_ID": "org-1",
    "AKUITY_INSTANCE_ID": "inst-1",
    "AKUITY_API_KEY": "secret",
    "SNOW_BASE_URL": "https://snow.example.com",
    "SNOW_API_KEY": "secret",
}


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    return monkeypatch


def test_defaults(env: pytest.MonkeyPatch) -> None:
    settings = Settings()
    assert settings.poll_interval_seconds == 15.0
    assert settings.stabilization_window_seconds == 300.0
    assert settings.akuity.app_label_selector == "env=prod"
    assert settings.snow.max_retries == 3
    assert settings.redis.url == "redis://localhost:6379/0"


def test_env_overrides(env: pytest.MonkeyPatch) -> None:
    env.setenv("POLL_INTERVAL_SECONDS", "5")
    env.setenv("STABILIZATION_WINDOW_SECONDS", "60")
    env.setenv("AKUITY_APP_LABEL_SELECTOR", "tier=critical")
    settings = Settings()
    assert settings.poll_interval_seconds == 5.0
    assert settings.stabilization_window_seconds == 60.0
    assert settings.akuity.app_label_selector == "tier=critical"


def test_secrets_loaded_from_env(env: pytest.MonkeyPatch) -> None:
    settings = Settings()
    assert settings.akuity.api_key == "secret"
    assert settings.snow.base_url == "https://snow.example.com"
