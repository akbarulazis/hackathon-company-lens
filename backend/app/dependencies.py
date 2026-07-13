"""Shared FastAPI dependency injection.

Provides reusable dependencies for database sessions, settings,
and Redis connections across all feature modules.
"""

from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.database import create_session_factory, get_session


@lru_cache
def get_cached_settings() -> Settings:
    """Return cached application settings (singleton)."""
    return get_settings()


def get_session_factory(
    settings: Settings = Depends(get_cached_settings),
) -> async_sessionmaker[AsyncSession]:
    """Provide the async session factory."""
    return create_session_factory(settings)


async def get_db(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional async database session."""
    async for session in get_session(session_factory):
        yield session


async def get_redis(
    settings: Settings = Depends(get_cached_settings),
) -> AsyncGenerator[Redis, None]:
    """Provide an async Redis connection."""
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()
