"""Authentication API router.

Provides endpoints for user registration, login, token refresh, and logout.
All error responses use generic messages to avoid leaking information about
which specific validation failed (e.g., never reveals whether username or
password was wrong on login).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenPair,
    UserResponse,
)
from app.auth.service import AuthError, login, logout, refresh_token, register
from app.config import Settings
from app.dependencies import get_cached_settings, get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RefreshRequest(BaseModel):
    """Refresh token request body."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout request body."""

    refresh_token: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Missing required fields"},
        409: {"model": ErrorResponse, "description": "Username or email already taken"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def register_user(
    data: RegisterRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_cached_settings),
) -> UserResponse:
    """Create a new user account.

    Validates all fields (username format, email format, password strength).
    Returns 400 if required fields are missing/empty.
    Returns 409 if username or email is already taken.
    Returns 422 if field validation fails (format, length, etc.).
    """
    # Check for empty/missing fields (Pydantic already handles missing,
    # but we need to check for empty strings explicitly)
    missing_fields = []
    if not data.username or not data.username.strip():
        missing_fields.append("username")
    if not data.email or not data.email.strip():
        missing_fields.append("email")
    if not data.password or not data.password.strip():
        missing_fields.append("password")

    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required fields: {', '.join(missing_fields)}",
        )

    try:
        return await register(session, data, settings)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post(
    "/login",
    response_model=TokenPair,
    responses={
        400: {"model": ErrorResponse, "description": "Missing required fields"},
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        429: {"model": ErrorResponse, "description": "Too many failed attempts"},
    },
)
async def login_user(
    data: LoginRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_cached_settings),
) -> TokenPair:
    """Authenticate user and return JWT token pair.

    Returns 400 if username or password is missing/empty.
    Returns 401 if credentials are invalid (generic message, never reveals
    whether username or password was wrong).
    Returns 429 if account is rate-limited due to too many failed attempts.
    """
    # Check for empty/missing fields
    missing_fields = []
    if not data.username or not data.username.strip():
        missing_fields.append("username")
    if not data.password or not data.password.strip():
        missing_fields.append("password")

    if missing_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required fields: {', '.join(missing_fields)}",
        )

    try:
        return await login(session, data, settings)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post(
    "/refresh",
    response_model=TokenPair,
    responses={
        400: {"model": ErrorResponse, "description": "Missing required fields"},
        401: {"model": ErrorResponse, "description": "Invalid or expired refresh token"},
    },
)
async def refresh_access_token(
    data: RefreshRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_cached_settings),
) -> TokenPair:
    """Refresh an access token using a valid refresh token.

    Returns 400 if refresh_token field is missing/empty.
    Returns 401 if refresh token is invalid, expired, or revoked.
    """
    if not data.refresh_token or not data.refresh_token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields: refresh_token",
        )

    try:
        return await refresh_token(session, data.refresh_token, settings)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Missing required fields"},
    },
)
async def logout_user(
    data: LogoutRequest,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Invalidate a refresh token (logout).

    Returns 400 if refresh_token field is missing/empty.
    Always returns success even if token doesn't exist (to avoid
    leaking information about token validity).
    """
    if not data.refresh_token or not data.refresh_token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields: refresh_token",
        )

    await logout(session, data.refresh_token)
    return {"detail": "Successfully logged out"}
