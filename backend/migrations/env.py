"""Alembic environment configuration for async migrations.

Uses SQLAlchemy async engine with asyncpg driver.
Imports all models to ensure metadata is populated before autogenerate.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.database import Base

# Import all models so that Base.metadata is fully populated
from app.auth.models import User, RefreshToken, LoginAttempt  # noqa: F401
from app.companies.models import CompanyProfile, ScoreSnapshot, CompanyRelationship  # noqa: F401
from app.workspaces.models import Workspace, WorkspaceCompany, ComparisonReport  # noqa: F401
from app.chatbot.models import ChatMessage  # noqa: F401
from app.documents.models import Document, TextChunk  # noqa: F401
from app.portfolio.models import PortfolioSnapshot, MetricCatalog, PortfolioSuggestion  # noqa: F401

# Alembic Config object
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def get_database_url() -> str:
    """Get async database URL from application settings."""
    settings = get_settings()
    return settings.async_database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a given connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using async engine."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
