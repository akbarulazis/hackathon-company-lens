"""Authentication service layer.

Business logic for registration, login, token management, and rate limiting.
Uses bcrypt for password hashing and python-jose for JWT operations.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import repository
from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenPair,
    UserResponse,
)
from app.config import Settings

# Rate limiting constants
MAX_FAILED_ATTEMPTS = 5
RATE_LIMIT_WINDOW_MINUTES = 15


class AuthError(Exception):
    """Base auth error with status code and message."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt. Never stores plaintext."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def _hash_token(token: str) -> str:
    """Compute SHA-256 hash of a refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: int, settings: Settings) -> str:
    """Create a JWT access token with 15-minute expiry."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token_value() -> str:
    """Generate a random UUID-based refresh token value."""
    return str(uuid.uuid4())


def decode_access_token(token: str, settings: Settings) -> dict:
    """Decode and validate an access token.

    Raises AuthError if token is expired, malformed, or not an access token.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise AuthError(status_code=401, detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise AuthError(status_code=401, detail="Invalid or expired token")

    return payload


async def register(
    session: AsyncSession, data: RegisterRequest, settings: Settings
) -> UserResponse:
    """Register a new user account.

    Validates username/email uniqueness, hashes password, creates user.
    Returns public user data on success.

    Raises:
        AuthError(409): If username or email already exists.
    """
    # Check username uniqueness
    existing_user = await repository.get_user_by_username(session, data.username)
    if existing_user:
        raise AuthError(
            status_code=409,
            detail="Username is already taken",
        )

    # Check email uniqueness
    existing_email = await repository.get_user_by_email(session, data.email)
    if existing_email:
        raise AuthError(
            status_code=409,
            detail="Email is already registered",
        )

    # Hash password and create user
    password_hashed = hash_password(data.password)
    user = await repository.create_user(
        session,
        username=data.username,
        email=data.email,
        password_hash=password_hashed,
    )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
    )


async def login(
    session: AsyncSession, data: LoginRequest, settings: Settings
) -> TokenPair:
    """Authenticate user and issue JWT token pair.

    Checks rate limit, verifies credentials, records attempt, generates tokens.

    Raises:
        AuthError(429): If account is rate-limited.
        AuthError(401): If credentials are invalid (generic message).
    """
    # Check rate limit before attempting login
    is_locked = await check_rate_limit(session, data.username)
    if is_locked:
        raise AuthError(
            status_code=429,
            detail="Too many failed login attempts. Please try again later.",
        )

    # Look up user
    user = await repository.get_user_by_username(session, data.username)

    if not user or not verify_password(data.password, user.password_hash):
        # Record failed attempt
        await repository.record_login_attempt(session, data.username, success=False)
        # Generic error — never reveal whether username or password was wrong
        raise AuthError(
            status_code=401,
            detail="Invalid credentials",
        )

    # Record successful attempt
    await repository.record_login_attempt(session, data.username, success=True)

    # Generate token pair
    access_token = create_access_token(user.id, settings)
    refresh_token_value = create_refresh_token_value()
    refresh_token_hash = _hash_token(refresh_token_value)

    # Store refresh token hash
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await repository.store_refresh_token(
        session,
        user_id=user.id,
        token_hash=refresh_token_hash,
        expires_at=expires_at,
    )

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token_value,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def refresh_token(
    session: AsyncSession, refresh_token_value: str, settings: Settings
) -> TokenPair:
    """Validate refresh token and issue a new token pair.

    Checks that the token exists, is not revoked, and is not expired.
    Issues a new access token and a new refresh token (rotating).

    Raises:
        AuthError(401): If refresh token is invalid, revoked, or expired.
    """
    token_hash = _hash_token(refresh_token_value)
    stored_token = await repository.get_refresh_token_by_hash(session, token_hash)

    if not stored_token:
        raise AuthError(status_code=401, detail="Invalid refresh token")

    if stored_token.revoked:
        raise AuthError(status_code=401, detail="Invalid refresh token")

    if stored_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise AuthError(status_code=401, detail="Invalid refresh token")

    # Revoke the old refresh token (rotation)
    await repository.revoke_refresh_token(session, token_hash)

    # Issue new token pair
    access_token = create_access_token(stored_token.user_id, settings)
    new_refresh_value = create_refresh_token_value()
    new_refresh_hash = _hash_token(new_refresh_value)

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    await repository.store_refresh_token(
        session,
        user_id=stored_token.user_id,
        token_hash=new_refresh_hash,
        expires_at=expires_at,
    )

    return TokenPair(
        access_token=access_token,
        refresh_token=new_refresh_value,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def logout(session: AsyncSession, refresh_token_value: str) -> None:
    """Invalidate (revoke) a refresh token.

    After logout, the refresh token can no longer be used to obtain
    new access tokens.
    """
    token_hash = _hash_token(refresh_token_value)
    await repository.revoke_refresh_token(session, token_hash)


async def check_rate_limit(session: AsyncSession, username: str) -> bool:
    """Check if a username is currently rate-limited.

    Returns True if the account is locked (5+ consecutive failures
    within the last 15 minutes), False otherwise.
    """
    since = datetime.now(timezone.utc) - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
    failed_count = await repository.get_recent_failed_attempts(session, username, since)
    return failed_count >= MAX_FAILED_ATTEMPTS
