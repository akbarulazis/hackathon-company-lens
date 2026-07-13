"""Application configuration using pydantic-settings.

All secrets are loaded from environment variables. The application
refuses to start if any required secret is missing or empty.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Required secrets: SECRET_KEY, OPENAI_API_KEY, TAVILY_API_KEY,
    DATABASE_URL, REDIS_URL.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Required secrets
    SECRET_KEY: str
    OPENAI_API_KEY: str
    TAVILY_API_KEY: str
    DATABASE_URL: str
    REDIS_URL: str

    # Application settings
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    APP_NAME: str = "Company Lens"
    API_PREFIX: str = "/api"

    # JWT settings
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Workspace settings
    WORKSPACE_COMPANY_LIMIT: int = 3

    @field_validator(
        "SECRET_KEY",
        "OPENAI_API_KEY",
        "TAVILY_API_KEY",
        "DATABASE_URL",
        "REDIS_URL",
        mode="before",
    )
    @classmethod
    def validate_not_empty(cls, v: str, info) -> str:
        """Refuse to start if any required secret is missing or empty."""
        if not v or not v.strip():
            raise ValueError(
                f"Required configuration '{info.field_name}' is missing or empty. "
                "The application cannot start without this value."
            )
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def async_database_url(self) -> str:
        """Convert database URL to async driver format if needed."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


def get_settings() -> Settings:
    """Create and validate settings from environment.

    Raises ValidationError if required secrets are missing or empty,
    which prevents the application from starting.
    """
    return Settings()  # type: ignore[call-arg]
