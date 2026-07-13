"""Property-based tests for auth service layer.

# Feature: company-lens-rebuild
# Property 3: Password Storage Never Contains Plaintext
# Property 4: Registration Uniqueness Enforcement
# Property 5: Token Lifecycle Round-Trip
# Property 6: Invalid Token Rejection Uniformity
# Property 7: Logout Invalidates Refresh Token

Validates: Requirements 1.2, 1.5, 2.1, 2.2, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3
"""

import hashlib
import string
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from jose import jwt

from app.auth.schemas import RegisterRequest
from app.auth.service import (
    AuthError,
    _hash_token,
    create_access_token,
    create_refresh_token_value,
    decode_access_token,
    hash_password,
    login,
    logout,
    refresh_token,
    register,
    verify_password,
)
from app.config import Settings

# ---------------------------------------------------------------------------
# Test Settings fixture
# ---------------------------------------------------------------------------

TEST_SECRET_KEY = "test-secret-key-for-property-testing-abc123"


def make_test_settings() -> Settings:
    """Create a Settings instance suitable for testing."""
    return Settings(
        SECRET_KEY=TEST_SECRET_KEY,
        OPENAI_API_KEY="test-openai-key",
        TAVILY_API_KEY="test-tavily-key",
        DATABASE_URL="postgresql://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        ACCESS_TOKEN_EXPIRE_MINUTES=15,
        REFRESH_TOKEN_EXPIRE_DAYS=7,
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Passwords that satisfy the schema validators (8-128 chars, upper, lower, digit, special)
PASSWORD_SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

valid_password_strategy = st.builds(
    lambda base, upper, lower, digit, special: upper + lower + digit + special + base,
    base=st.text(
        alphabet=string.ascii_letters + string.digits,
        min_size=0,
        max_size=60,
    ),
    upper=st.text(alphabet=string.ascii_uppercase, min_size=1, max_size=2),
    lower=st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=2),
    digit=st.text(alphabet=string.digits, min_size=1, max_size=2),
    special=st.sampled_from(list(PASSWORD_SPECIAL_CHARS)),
).filter(lambda p: 8 <= len(p) <= 72)  # bcrypt max input is 72 bytes

# Valid usernames for registration (3-50 chars, alphanumeric + _ -)
USERNAME_VALID_CHARS = string.ascii_letters + string.digits + "_-"
valid_username_strategy = st.text(
    alphabet=st.sampled_from(USERNAME_VALID_CHARS),
    min_size=3,
    max_size=30,
)

# Valid emails for registration
valid_email_strategy = st.builds(
    lambda local, domain, tld: f"{local}@{domain}.{tld}",
    local=st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=15),
    domain=st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=10),
    tld=st.text(alphabet=string.ascii_lowercase, min_size=2, max_size=5),
)

# Arbitrary non-empty text for tampered tokens
arbitrary_token_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=200,
)


# ===========================================================================
# Property 3: Password Storage Never Contains Plaintext
# ===========================================================================


@given(password=valid_password_strategy)
@settings(max_examples=50, deadline=None)
def test_property3_hash_never_equals_plaintext(password: str) -> None:
    """Property 3: For any password, the bcrypt hash MUST never equal the
    plaintext password itself.

    **Validates: Requirements 1.2, 1.5**
    """
    hashed = hash_password(password)
    assert hashed != password, "Hash must never equal plaintext"


@given(password=valid_password_strategy)
@settings(max_examples=50, deadline=None)
def test_property3_hash_verifies_against_original(password: str) -> None:
    """Property 3: For any password, verify_password(original, hash) MUST
    return True — proving the hash was derived from the original.

    **Validates: Requirements 1.2, 1.5**
    """
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


@given(
    password=valid_password_strategy,
    other_password=valid_password_strategy,
)
@settings(max_examples=50, deadline=None)
def test_property3_hash_does_not_verify_different_password(
    password: str, other_password: str
) -> None:
    """Property 3: For any two distinct passwords, verify_password(other, hash)
    MUST return False — the hash only verifies against its original input.

    **Validates: Requirements 1.2, 1.5**
    """
    if password == other_password:
        return  # skip trivially equal inputs
    hashed = hash_password(password)
    assert verify_password(other_password, hashed) is False


# ===========================================================================
# Property 4: Registration Uniqueness Enforcement
# ===========================================================================


@given(
    username=valid_username_strategy,
    email=valid_email_strategy,
    password=valid_password_strategy,
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property4_duplicate_username_rejected(
    username: str, email: str, password: str
) -> None:
    """Property 4: Registering with a username that already exists MUST be
    rejected with a 409 error containing a descriptive message.

    **Validates: Requirements 2.1, 2.2**
    """
    test_settings = make_test_settings()
    mock_session = AsyncMock()

    # Simulate existing user with same username
    existing_user = MagicMock()
    existing_user.username = username

    with patch("app.auth.service.repository") as mock_repo:
        mock_repo.get_user_by_username = AsyncMock(return_value=existing_user)

        data = RegisterRequest.model_construct(
            username=username,
            email=email,
            password=password,
        )

        with pytest.raises(AuthError) as exc_info:
            await register(mock_session, data, test_settings)

        assert exc_info.value.status_code == 409
        assert "username" in exc_info.value.detail.lower()


@given(
    username=valid_username_strategy,
    email=valid_email_strategy,
    password=valid_password_strategy,
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property4_duplicate_email_rejected(
    username: str, email: str, password: str
) -> None:
    """Property 4: Registering with an email that already exists MUST be
    rejected with a 409 error containing a descriptive message.

    **Validates: Requirements 2.1, 2.2**
    """
    test_settings = make_test_settings()
    mock_session = AsyncMock()

    # Username is unique, but email is taken
    existing_email_user = MagicMock()
    existing_email_user.email = email

    with patch("app.auth.service.repository") as mock_repo:
        mock_repo.get_user_by_username = AsyncMock(return_value=None)
        mock_repo.get_user_by_email = AsyncMock(return_value=existing_email_user)

        data = RegisterRequest.model_construct(
            username=username,
            email=email,
            password=password,
        )

        with pytest.raises(AuthError) as exc_info:
            await register(mock_session, data, test_settings)

        assert exc_info.value.status_code == 409
        assert "email" in exc_info.value.detail.lower()


# ===========================================================================
# Property 5: Token Lifecycle Round-Trip
# ===========================================================================


@given(user_id=st.integers(min_value=1, max_value=100_000))
@settings(max_examples=200)
def test_property5_access_token_round_trip(user_id: int) -> None:
    """Property 5: Creating an access token and decoding it MUST yield a
    payload containing the original user_id as 'sub'.

    **Validates: Requirements 2.4, 2.5**
    """
    test_settings = make_test_settings()
    token = create_access_token(user_id, test_settings)
    payload = decode_access_token(token, test_settings)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"


@given(
    username=valid_username_strategy,
    password=valid_password_strategy,
)
@settings(max_examples=50, deadline=None)
@pytest.mark.asyncio
async def test_property5_login_produces_valid_token_pair(
    username: str, password: str
) -> None:
    """Property 5: A successful login MUST produce a TokenPair where:
    - access_token decodes to a valid payload with the user's id
    - refresh_token is a non-empty string

    **Validates: Requirements 2.4, 2.5, 2.6**
    """
    test_settings = make_test_settings()
    mock_session = AsyncMock()

    # Create a mock user with hashed password
    hashed_pw = hash_password(password)
    mock_user = MagicMock()
    mock_user.id = 42
    mock_user.username = username
    mock_user.password_hash = hashed_pw

    with patch("app.auth.service.repository") as mock_repo:
        mock_repo.get_user_by_username = AsyncMock(return_value=mock_user)
        mock_repo.record_login_attempt = AsyncMock()
        mock_repo.store_refresh_token = AsyncMock()
        # Not rate limited
        mock_repo.get_recent_failed_attempts = AsyncMock(return_value=0)

        from app.auth.schemas import LoginRequest

        data = LoginRequest.model_construct(username=username, password=password)
        token_pair = await login(mock_session, data, test_settings)

        # access_token should decode successfully
        payload = decode_access_token(token_pair.access_token, test_settings)
        assert payload["sub"] == str(mock_user.id)

        # refresh_token should be a non-empty string (UUID format)
        assert len(token_pair.refresh_token) > 0
        # Verify it's a valid UUID
        uuid.UUID(token_pair.refresh_token)


@given(user_id=st.integers(min_value=1, max_value=100_000))
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property5_refresh_yields_new_access_token(user_id: int) -> None:
    """Property 5: Refreshing a valid, non-revoked, non-expired token MUST
    produce a new TokenPair with a valid access token for the same user.

    **Validates: Requirements 2.5, 2.6**
    """
    test_settings = make_test_settings()
    mock_session = AsyncMock()

    # Simulate an existing valid refresh token in DB
    refresh_value = str(uuid.uuid4())
    token_hash = hashlib.sha256(refresh_value.encode()).hexdigest()

    mock_stored_token = MagicMock()
    mock_stored_token.user_id = user_id
    mock_stored_token.revoked = False
    mock_stored_token.expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    with patch("app.auth.service.repository") as mock_repo:
        mock_repo.get_refresh_token_by_hash = AsyncMock(return_value=mock_stored_token)
        mock_repo.revoke_refresh_token = AsyncMock()
        mock_repo.store_refresh_token = AsyncMock()

        new_pair = await refresh_token(mock_session, refresh_value, test_settings)

        # New access token should decode to the same user
        payload = decode_access_token(new_pair.access_token, test_settings)
        assert payload["sub"] == str(user_id)

        # New refresh token should be different from old one
        assert new_pair.refresh_token != refresh_value


# ===========================================================================
# Property 6: Invalid Token Rejection Uniformity
# ===========================================================================


@given(token_text=arbitrary_token_text)
@settings(max_examples=200)
def test_property6_malformed_tokens_rejected_with_401(token_text: str) -> None:
    """Property 6: Any malformed (non-JWT) string MUST be rejected by
    decode_access_token with a 401 AuthError.

    **Validates: Requirements 3.1, 3.2**
    """
    test_settings = make_test_settings()
    with pytest.raises(AuthError) as exc_info:
        decode_access_token(token_text, test_settings)
    assert exc_info.value.status_code == 401


@given(user_id=st.integers(min_value=1, max_value=100_000))
@settings(max_examples=200)
def test_property6_expired_tokens_rejected_with_401(user_id: int) -> None:
    """Property 6: A JWT that has expired MUST be rejected with a 401 AuthError.

    **Validates: Requirements 3.1, 3.2**
    """
    test_settings = make_test_settings()

    # Create a token that expired 1 hour ago
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "exp": now - timedelta(hours=1),
        "type": "access",
    }
    expired_token = jwt.encode(payload, test_settings.SECRET_KEY, algorithm="HS256")

    with pytest.raises(AuthError) as exc_info:
        decode_access_token(expired_token, test_settings)
    assert exc_info.value.status_code == 401


@given(user_id=st.integers(min_value=1, max_value=100_000))
@settings(max_examples=200)
def test_property6_wrong_secret_tokens_rejected_with_401(user_id: int) -> None:
    """Property 6: A JWT signed with a different secret MUST be rejected
    with a 401 AuthError (tampered token detection).

    **Validates: Requirements 3.1, 3.2, 3.3**
    """
    test_settings = make_test_settings()

    # Sign with a wrong key
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "exp": now + timedelta(hours=1),
        "type": "access",
    }
    tampered_token = jwt.encode(payload, "wrong-secret-key", algorithm="HS256")

    with pytest.raises(AuthError) as exc_info:
        decode_access_token(tampered_token, test_settings)
    assert exc_info.value.status_code == 401


@given(user_id=st.integers(min_value=1, max_value=100_000))
@settings(max_examples=200)
def test_property6_wrong_token_type_rejected_with_401(user_id: int) -> None:
    """Property 6: A JWT with type != 'access' MUST be rejected with a
    401 AuthError, even if otherwise valid.

    **Validates: Requirements 3.1, 3.2**
    """
    test_settings = make_test_settings()

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "exp": now + timedelta(hours=1),
        "type": "refresh",  # wrong type
    }
    wrong_type_token = jwt.encode(payload, test_settings.SECRET_KEY, algorithm="HS256")

    with pytest.raises(AuthError) as exc_info:
        decode_access_token(wrong_type_token, test_settings)
    assert exc_info.value.status_code == 401


# ===========================================================================
# Property 7: Logout Invalidates Refresh Token
# ===========================================================================


@given(user_id=st.integers(min_value=1, max_value=100_000))
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property7_logout_revokes_refresh_token(user_id: int) -> None:
    """Property 7: After logout, the refresh token MUST be revoked such that
    a subsequent refresh attempt is rejected with a 401 error.

    **Validates: Requirements 3.1, 3.3**
    """
    test_settings = make_test_settings()
    mock_session = AsyncMock()

    refresh_value = str(uuid.uuid4())
    token_hash = hashlib.sha256(refresh_value.encode()).hexdigest()

    # Track revocation state
    revoked = {"value": False}

    async def mock_revoke(session, th):
        revoked["value"] = True

    # After logout, the stored token should appear revoked
    mock_stored_token = MagicMock()
    mock_stored_token.user_id = user_id
    mock_stored_token.revoked = False
    mock_stored_token.expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    with patch("app.auth.service.repository") as mock_repo:
        mock_repo.revoke_refresh_token = AsyncMock(side_effect=mock_revoke)

        # Perform logout
        await logout(mock_session, refresh_value)

        # Verify revoke was called with the correct token hash
        mock_repo.revoke_refresh_token.assert_called_once_with(mock_session, token_hash)
        assert revoked["value"] is True


@given(user_id=st.integers(min_value=1, max_value=100_000))
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property7_refresh_after_logout_rejected(user_id: int) -> None:
    """Property 7: After a refresh token is revoked (via logout), attempting
    to use it for refresh MUST raise AuthError with status 401.

    **Validates: Requirements 3.1, 3.3**
    """
    test_settings = make_test_settings()
    mock_session = AsyncMock()

    refresh_value = str(uuid.uuid4())

    # Simulate a revoked token in DB
    mock_stored_token = MagicMock()
    mock_stored_token.user_id = user_id
    mock_stored_token.revoked = True  # Already revoked by logout
    mock_stored_token.expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    with patch("app.auth.service.repository") as mock_repo:
        mock_repo.get_refresh_token_by_hash = AsyncMock(return_value=mock_stored_token)

        with pytest.raises(AuthError) as exc_info:
            await refresh_token(mock_session, refresh_value, test_settings)

        assert exc_info.value.status_code == 401
