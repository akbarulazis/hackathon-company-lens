"""Authentication dependencies for FastAPI route protection.

Provides get_current_user dependency that validates JWT access tokens
on protected routes. Returns 401 for any invalid token without revealing
specifics about why the token was rejected.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import repository
from app.auth.models import User
from app.auth.service import AuthError, decode_access_token
from app.config import Settings
from app.dependencies import get_cached_settings, get_db

# Use auto_error=False so we can return a consistent 401 message
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_cached_settings),
) -> User:
    """Validate JWT access token and return the authenticated user.

    Extracts the Bearer token from the Authorization header, decodes it,
    and verifies the user exists in the database.

    Returns:
        The authenticated User instance.

    Raises:
        HTTPException(401): If token is missing, expired, malformed,
            tampered, or the user no longer exists. The error message
            is always generic to avoid leaking information.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials, settings)
    except AuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user ID from token subject
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify user still exists
    user = await repository.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
