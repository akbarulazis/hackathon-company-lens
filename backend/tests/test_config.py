"""Tests for application configuration and startup validation."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def _make_env(**overrides) -> dict[str, str]:
    """Create a complete valid environment dict with optional overrides."""
    defaults = {
        "SECRET_KEY": "test-secret-key-12345",
        "OPENAI_API_KEY": "sk-test-openai-key",
        "TAVILY_API_KEY": "tvly-test-tavily-key",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/testdb",
        "REDIS_URL": "redis://localhost:6379/0",
    }
    defaults.update(overrides)
    return defaults


class TestSettingsValidation:
    """Test that required secrets are validated at startup."""

    def test_valid_settings_created_successfully(self, monkeypatch):
        """Settings are created when all required secrets are present."""
        env = _make_env()
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        settings = Settings()  # type: ignore[call-arg]

        assert settings.SECRET_KEY == "test-secret-key-12345"
        assert settings.OPENAI_API_KEY == "sk-test-openai-key"
        assert settings.TAVILY_API_KEY == "tvly-test-tavily-key"
        assert settings.DATABASE_URL == "postgresql://user:pass@localhost:5432/testdb"
        assert settings.REDIS_URL == "redis://localhost:6379/0"

    @pytest.mark.parametrize(
        "missing_key",
        ["SECRET_KEY", "OPENAI_API_KEY", "TAVILY_API_KEY", "DATABASE_URL", "REDIS_URL"],
    )
    def test_refuses_to_start_with_missing_secret(self, monkeypatch, missing_key):
        """Application refuses to start if any required secret is missing."""
        env = _make_env()
        del env[missing_key]
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv(missing_key, raising=False)

        with pytest.raises(ValidationError):
            Settings()  # type: ignore[call-arg]

    @pytest.mark.parametrize(
        "empty_key",
        ["SECRET_KEY", "OPENAI_API_KEY", "TAVILY_API_KEY", "DATABASE_URL", "REDIS_URL"],
    )
    def test_refuses_to_start_with_empty_secret(self, monkeypatch, empty_key):
        """Application refuses to start if any required secret is empty."""
        env = _make_env(**{empty_key: ""})
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        with pytest.raises(ValidationError):
            Settings()  # type: ignore[call-arg]

    @pytest.mark.parametrize(
        "whitespace_key",
        ["SECRET_KEY", "OPENAI_API_KEY", "TAVILY_API_KEY", "DATABASE_URL", "REDIS_URL"],
    )
    def test_refuses_to_start_with_whitespace_only_secret(self, monkeypatch, whitespace_key):
        """Application refuses to start if a required secret is only whitespace."""
        env = _make_env(**{whitespace_key: "   "})
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        with pytest.raises(ValidationError):
            Settings()  # type: ignore[call-arg]


class TestSettingsDefaults:
    """Test default configuration values."""

    def test_default_environment(self, monkeypatch):
        env = _make_env()
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        settings = Settings()  # type: ignore[call-arg]

        assert settings.ENVIRONMENT == "development"
        assert settings.DEBUG is False
        assert settings.is_production is False

    def test_production_environment(self, monkeypatch):
        env = _make_env(ENVIRONMENT="production")
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        settings = Settings()  # type: ignore[call-arg]

        assert settings.is_production is True

    def test_default_jwt_settings(self, monkeypatch):
        env = _make_env()
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        settings = Settings()  # type: ignore[call-arg]

        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 15
        assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 7

    def test_default_workspace_company_limit(self, monkeypatch):
        env = _make_env()
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        settings = Settings()  # type: ignore[call-arg]

        assert settings.WORKSPACE_COMPANY_LIMIT == 3


class TestAsyncDatabaseUrl:
    """Test database URL conversion to async driver format."""

    def test_converts_postgresql_to_asyncpg(self, monkeypatch):
        env = _make_env(DATABASE_URL="postgresql://user:pass@localhost:5432/db")
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        settings = Settings()  # type: ignore[call-arg]

        assert settings.async_database_url == "postgresql+asyncpg://user:pass@localhost:5432/db"

    def test_converts_postgres_to_asyncpg(self, monkeypatch):
        env = _make_env(DATABASE_URL="postgres://user:pass@localhost:5432/db")
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        settings = Settings()  # type: ignore[call-arg]

        assert settings.async_database_url == "postgresql+asyncpg://user:pass@localhost:5432/db"

    def test_preserves_existing_asyncpg_url(self, monkeypatch):
        env = _make_env(DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db")
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        settings = Settings()  # type: ignore[call-arg]

        assert settings.async_database_url == "postgresql+asyncpg://user:pass@localhost:5432/db"
