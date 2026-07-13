"""Async SQLAlchemy engine and session factory.

Uses SQLAlchemy 2.0 async sessions with asyncpg driver.
All database operations are async-only — no synchronous blocking.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import Settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    pass


def create_engine(settings: Settings):
    """Create async SQLAlchemy engine from settings."""
    return create_async_engine(
        settings.async_database_url,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


def create_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """Create async session factory bound to the engine."""
    # Ensure all models are imported so relationships resolve
    import app.models  # noqa: F401

    engine = create_engine(settings)
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session, ensuring proper cleanup."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
