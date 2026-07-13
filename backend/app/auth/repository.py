"""Authentication repository layer.

Provides database operations for users, refresh tokens, and login attempts.
No business logic — only data access via SQLAlchemy async sessions.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import LoginAttempt, RefreshToken, User


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Fetch a user by primary key ID."""
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    """Fetch a user by username (case-sensitive match)."""
    result = await session.execute(
        select(User).where(User.username == username)
    )
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Fetch a user by email (case-sensitive match)."""
    result = await session.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    username: str,
    email: str,
    password_hash: str,
) -> User:
    """Create a new user and flush to obtain the generated ID."""
    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
    )
    session.add(user)
    await session.flush()
    return user


async def store_refresh_token(
    session: AsyncSession,
    user_id: int,
    token_hash: str,
    expires_at: datetime,
) -> RefreshToken:
    """Store a hashed refresh token for a user."""
    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(refresh_token)
    await session.flush()
    return refresh_token


async def get_refresh_token_by_hash(
    session: AsyncSession, token_hash: str
) -> RefreshToken | None:
    """Look up a refresh token by its SHA-256 hash."""
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    return result.scalar_one_or_none()


async def revoke_refresh_token(session: AsyncSession, token_hash: str) -> None:
    """Mark a refresh token as revoked."""
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()
    if token:
        token.revoked = True
        await session.flush()


async def record_login_attempt(
    session: AsyncSession, username: str, success: bool
) -> None:
    """Record a login attempt for rate-limiting purposes."""
    attempt = LoginAttempt(
        username=username,
        success=success,
    )
    session.add(attempt)
    await session.flush()


async def get_recent_failed_attempts(
    session: AsyncSession, username: str, since: datetime
) -> int:
    """Count consecutive failed login attempts since a given timestamp.

    Counts failures after the most recent success (if any) within the window.
    If there was a successful login after any failures, only failures after
    that success are counted.
    """
    # Find the most recent successful login in the window
    last_success_query = (
        select(func.max(LoginAttempt.attempted_at))
        .where(
            LoginAttempt.username == username,
            LoginAttempt.success.is_(True),
            LoginAttempt.attempted_at >= since,
        )
    )
    last_success_result = await session.execute(last_success_query)
    last_success_at = last_success_result.scalar_one_or_none()

    # Count failures after the last success (or from the window start)
    cutoff = last_success_at if last_success_at else since

    count_query = (
        select(func.count())
        .select_from(LoginAttempt)
        .where(
            LoginAttempt.username == username,
            LoginAttempt.success.is_(False),
            LoginAttempt.attempted_at >= cutoff,
        )
    )
    result = await session.execute(count_query)
    return result.scalar_one()
