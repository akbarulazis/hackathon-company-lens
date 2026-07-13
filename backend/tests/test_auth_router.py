"""Tests for auth router endpoints and get_current_user dependency.

Tests the HTTP-level behavior of /api/auth/* endpoints:
- POST /register
- POST /login
- POST /refresh
- POST /logout

Also tests the get_current_user dependency for JWT validation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from app.auth.router import router
from app.auth.schemas import TokenPair, UserResponse
from app.auth.service import AuthError, create_access_token
from app.config import Settings


def _make_test_settings() -> Settings:
    """Create test settings without environment dependency."""
    return Settings(
        SECRET_KEY="test-secret-key-for-unit-tests",
        OPENAI_API_KEY="test-openai-key",
        TAVILY_API_KEY="test-tavily-key",
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
    )


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with auth router for testing."""
    from app.auth.dependencies import get_current_user
    from app.dependencies import get_cached_settings, get_db

    app = FastAPI()
    app.include_router(router)

    # Override settings dependency
    settings = _make_test_settings()
    app.dependency_overrides[get_cached_settings] = lambda: settings

    return app


class TestRegisterEndpoint:
    """Tests for POST /api/auth/register."""

    def setup_method(self):
        self.app = _create_test_app()
        self.client = TestClient(self.app)

    @patch("app.auth.router.register")
    def test_register_success(self, mock_register):
        """Successful registration returns 201 with user data."""
        mock_register.return_value = UserResponse(
            id=1, username="testuser", email="test@example.com"
        )

        # Override DB dependency with mock
        mock_session = AsyncMock()
        self.app.dependency_overrides[
            __import__("app.dependencies", fromlist=["get_db"]).get_db
        ] = lambda: mock_session

        from app.dependencies import get_db
        self.app.dependency_overrides[get_db] = lambda: mock_session

        response = self.client.post(
            "/api/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "StrongPass1!",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 1
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"

    def test_register_missing_body_returns_422(self):
        """Request with no body returns 422 (Pydantic validation)."""
        response = self.client.post("/api/auth/register")
        assert response.status_code == 422

    @patch("app.auth.router.register")
    def test_register_duplicate_username_returns_409(self, mock_register):
        """Duplicate username returns 409."""
        mock_register.side_effect = AuthError(
            status_code=409, detail="Username is already taken"
        )

        from app.dependencies import get_db
        mock_session = AsyncMock()
        self.app.dependency_overrides[get_db] = lambda: mock_session

        response = self.client.post(
            "/api/auth/register",
            json={
                "username": "existing",
                "email": "new@example.com",
                "password": "StrongPass1!",
            },
        )

        assert response.status_code == 409
        assert "already taken" in response.json()["detail"]

    @patch("app.auth.router.register")
    def test_register_duplicate_email_returns_409(self, mock_register):
        """Duplicate email returns 409."""
        mock_register.side_effect = AuthError(
            status_code=409, detail="Email is already registered"
        )

        from app.dependencies import get_db
        mock_session = AsyncMock()
        self.app.dependency_overrides[get_db] = lambda: mock_session

        response = self.client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "existing@example.com",
                "password": "StrongPass1!",
            },
        )

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    def test_register_invalid_password_returns_422(self):
        """Weak password returns 422 via Pydantic validation."""
        from app.dependencies import get_db
        mock_session = AsyncMock()
        self.app.dependency_overrides[get_db] = lambda: mock_session

        response = self.client.post(
            "/api/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "weak",
            },
        )

        assert response.status_code == 422


class TestLoginEndpoint:
    """Tests for POST /api/auth/login."""

    def setup_method(self):
        self.app = _create_test_app()
        self.client = TestClient(self.app)

        from app.dependencies import get_db
        self.mock_session = AsyncMock()
        self.app.dependency_overrides[get_db] = lambda: self.mock_session

    @patch("app.auth.router.login")
    def test_login_success(self, mock_login):
        """Successful login returns 200 with token pair."""
        mock_login.return_value = TokenPair(
            access_token="access.token.here",
            refresh_token="refresh-token-uuid",
            token_type="bearer",
            expires_in=900,
        )

        response = self.client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "StrongPass1!"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "access.token.here"
        assert data["refresh_token"] == "refresh-token-uuid"
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 900

    @patch("app.auth.router.login")
    def test_login_invalid_credentials_returns_401(self, mock_login):
        """Invalid credentials returns 401 with generic message."""
        mock_login.side_effect = AuthError(
            status_code=401, detail="Invalid credentials"
        )

        response = self.client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "WrongPass1!"},
        )

        assert response.status_code == 401
        # Should not reveal whether username or password was wrong
        assert "Invalid credentials" in response.json()["detail"]
        assert "username" not in response.json()["detail"].lower()
        assert "password" not in response.json()["detail"].lower()

    @patch("app.auth.router.login")
    def test_login_rate_limited_returns_429(self, mock_login):
        """Rate-limited account returns 429."""
        mock_login.side_effect = AuthError(
            status_code=429,
            detail="Too many failed login attempts. Please try again later.",
        )

        response = self.client.post(
            "/api/auth/login",
            json={"username": "lockeduser", "password": "Pass1!"},
        )

        assert response.status_code == 429

    def test_login_empty_username_returns_400(self):
        """Empty username returns 400."""
        response = self.client.post(
            "/api/auth/login",
            json={"username": "", "password": "StrongPass1!"},
        )

        assert response.status_code == 400
        assert "username" in response.json()["detail"].lower()

    def test_login_empty_password_returns_400(self):
        """Empty password returns 400."""
        response = self.client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": ""},
        )

        assert response.status_code == 400
        assert "password" in response.json()["detail"].lower()

    def test_login_missing_body_returns_422(self):
        """Missing request body returns 422."""
        response = self.client.post("/api/auth/login")
        assert response.status_code == 422


class TestRefreshEndpoint:
    """Tests for POST /api/auth/refresh."""

    def setup_method(self):
        self.app = _create_test_app()
        self.client = TestClient(self.app)

        from app.dependencies import get_db
        self.mock_session = AsyncMock()
        self.app.dependency_overrides[get_db] = lambda: self.mock_session

    @patch("app.auth.router.refresh_token")
    def test_refresh_success(self, mock_refresh):
        """Valid refresh token returns new token pair."""
        mock_refresh.return_value = TokenPair(
            access_token="new.access.token",
            refresh_token="new-refresh-uuid",
            token_type="bearer",
            expires_in=900,
        )

        response = self.client.post(
            "/api/auth/refresh",
            json={"refresh_token": "valid-refresh-uuid"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "new.access.token"
        assert data["refresh_token"] == "new-refresh-uuid"

    @patch("app.auth.router.refresh_token")
    def test_refresh_invalid_token_returns_401(self, mock_refresh):
        """Invalid refresh token returns 401."""
        mock_refresh.side_effect = AuthError(
            status_code=401, detail="Invalid refresh token"
        )

        response = self.client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )

        assert response.status_code == 401

    @patch("app.auth.router.refresh_token")
    def test_refresh_expired_token_returns_401(self, mock_refresh):
        """Expired refresh token returns 401."""
        mock_refresh.side_effect = AuthError(
            status_code=401, detail="Invalid refresh token"
        )

        response = self.client.post(
            "/api/auth/refresh",
            json={"refresh_token": "expired-token"},
        )

        assert response.status_code == 401

    def test_refresh_empty_token_returns_400(self):
        """Empty refresh_token returns 400."""
        response = self.client.post(
            "/api/auth/refresh",
            json={"refresh_token": ""},
        )

        assert response.status_code == 400
        assert "refresh_token" in response.json()["detail"].lower()

    def test_refresh_missing_body_returns_422(self):
        """Missing body returns 422."""
        response = self.client.post("/api/auth/refresh")
        assert response.status_code == 422


class TestLogoutEndpoint:
    """Tests for POST /api/auth/logout."""

    def setup_method(self):
        self.app = _create_test_app()
        self.client = TestClient(self.app)

        from app.dependencies import get_db
        self.mock_session = AsyncMock()
        self.app.dependency_overrides[get_db] = lambda: self.mock_session

    @patch("app.auth.router.logout")
    def test_logout_success(self, mock_logout):
        """Valid logout returns 200."""
        mock_logout.return_value = None

        response = self.client.post(
            "/api/auth/logout",
            json={"refresh_token": "valid-token"},
        )

        assert response.status_code == 200
        assert "logged out" in response.json()["detail"].lower()

    @patch("app.auth.router.logout")
    def test_logout_nonexistent_token_still_returns_200(self, mock_logout):
        """Logout with non-existent token still returns 200 (no info leakage)."""
        mock_logout.return_value = None

        response = self.client.post(
            "/api/auth/logout",
            json={"refresh_token": "nonexistent-token"},
        )

        assert response.status_code == 200

    def test_logout_empty_token_returns_400(self):
        """Empty refresh_token returns 400."""
        response = self.client.post(
            "/api/auth/logout",
            json={"refresh_token": ""},
        )

        assert response.status_code == 400

    def test_logout_missing_body_returns_422(self):
        """Missing body returns 422."""
        response = self.client.post("/api/auth/logout")
        assert response.status_code == 422


class TestGetCurrentUserDependency:
    """Tests for the get_current_user dependency."""

    def setup_method(self):
        from app.auth.dependencies import get_current_user
        from app.dependencies import get_cached_settings, get_db

        self.app = FastAPI()
        self.settings = _make_test_settings()

        # Create a protected endpoint using the dependency
        @self.app.get("/protected")
        async def protected_route(user=Depends(get_current_user)):
            return {"user_id": user.id, "username": user.username}

        self.app.dependency_overrides[get_cached_settings] = lambda: self.settings
        self.client = TestClient(self.app)

    def test_no_auth_header_returns_401(self):
        """Missing Authorization header returns 401."""
        response = self.client.get("/protected")
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired token"

    def test_invalid_token_returns_401(self):
        """Malformed token returns 401."""
        response = self.client.get(
            "/protected",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired token"

    def test_expired_token_returns_401(self):
        """Expired token returns 401."""
        from jose import jwt

        # Create an expired token
        payload = {
            "sub": "1",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "type": "access",
        }
        expired_token = jwt.encode(payload, self.settings.SECRET_KEY, algorithm="HS256")

        response = self.client.get(
            "/protected",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401

    def test_tampered_token_returns_401(self):
        """Token signed with wrong key returns 401."""
        from jose import jwt

        payload = {
            "sub": "1",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "access",
        }
        tampered_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        response = self.client.get(
            "/protected",
            headers={"Authorization": f"Bearer {tampered_token}"},
        )
        assert response.status_code == 401

    @patch("app.auth.dependencies.repository.get_user_by_id")
    def test_valid_token_with_existing_user_succeeds(self, mock_get_user):
        """Valid token for existing user returns user data."""
        from app.dependencies import get_db

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_get_user.return_value = mock_user

        mock_session = AsyncMock()
        self.app.dependency_overrides[get_db] = lambda: mock_session

        # Create a valid token
        token = create_access_token(1, self.settings)

        response = self.client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == 1
        assert response.json()["username"] == "testuser"

    @patch("app.auth.dependencies.repository.get_user_by_id")
    def test_valid_token_deleted_user_returns_401(self, mock_get_user):
        """Valid token for a deleted user returns 401."""
        from app.dependencies import get_db

        mock_get_user.return_value = None
        mock_session = AsyncMock()
        self.app.dependency_overrides[get_db] = lambda: mock_session

        token = create_access_token(999, self.settings)

        response = self.client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    def test_refresh_token_type_returns_401(self):
        """A refresh-type token (not access) returns 401."""
        from jose import jwt

        payload = {
            "sub": "1",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "refresh",  # Wrong type
        }
        token = jwt.encode(payload, self.settings.SECRET_KEY, algorithm="HS256")

        from app.dependencies import get_db
        mock_session = AsyncMock()
        self.app.dependency_overrides[get_db] = lambda: mock_session

        response = self.client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    def test_401_response_never_reveals_specifics(self):
        """All 401 responses use the same generic message."""
        # No header
        r1 = self.client.get("/protected")
        # Bad token
        r2 = self.client.get(
            "/protected",
            headers={"Authorization": "Bearer garbage"},
        )
        # All should have the same detail
        assert r1.json()["detail"] == "Invalid or expired token"
        assert r2.json()["detail"] == "Invalid or expired token"


# Need Depends import for the test app
from fastapi import Depends
