"""Property-based tests for auth validators.

# Feature: company-lens-rebuild
# Property 1: Password Validation Correctness
# Property 2: Username and Email Format Validation
# Property 40: Pydantic Input Length Validation

Validates: Requirements 1.3, 1.4, 1.6, 18.6
"""

import re
import string

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    validate_email,
    validate_password,
    validate_username,
)

# ---------------------------------------------------------------------------
# Constants mirrored from schemas (so tests are self-contained / explicit)
# ---------------------------------------------------------------------------
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PASSWORD_SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 50
USERNAME_VALID_CHARS = string.ascii_letters + string.digits + "_-"

EMAIL_MAX_LENGTH = 255
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

MAX_IDENTIFIER_LENGTH = 255
MAX_FREE_TEXT_LENGTH = 10_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_uppercase(s: str) -> bool:
    return bool(re.search(r"[A-Z]", s))


def _has_lowercase(s: str) -> bool:
    return bool(re.search(r"[a-z]", s))


def _has_digit(s: str) -> bool:
    return bool(re.search(r"\d", s))


def _has_special(s: str) -> bool:
    return bool(re.search(r"[!@#$%^&*()_+=\[\]{}|;:,.<>?\-]", s))


def _password_meets_spec(s: str) -> bool:
    """Return True iff the string satisfies every password requirement."""
    return (
        PASSWORD_MIN_LENGTH <= len(s) <= PASSWORD_MAX_LENGTH
        and _has_uppercase(s)
        and _has_lowercase(s)
        and _has_digit(s)
        and _has_special(s)
    )


def _username_meets_spec(s: str) -> bool:
    return bool(re.fullmatch(r"[a-zA-Z0-9_-]{3,50}", s))


def _email_meets_spec(s: str) -> bool:
    return len(s) <= EMAIL_MAX_LENGTH and bool(EMAIL_PATTERN.match(s))


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# A valid password satisfying all requirements
valid_password_strategy = st.builds(
    lambda base, upper, lower, digit, special: upper + lower + digit + special + base,
    base=st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="_+-=",
        ),
        min_size=0,
        max_size=120,
    ),
    upper=st.text(alphabet=string.ascii_uppercase, min_size=1, max_size=2),
    lower=st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=2),
    digit=st.text(alphabet=string.digits, min_size=1, max_size=2),
    special=st.sampled_from(list(PASSWORD_SPECIAL_CHARS)),
).filter(lambda p: PASSWORD_MIN_LENGTH <= len(p) <= PASSWORD_MAX_LENGTH)

# Arbitrary text – used to check the validator correctly rejects bad strings
arbitrary_text_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=0,
    max_size=200,
)

# Valid username: 3-50 chars from [a-zA-Z0-9_-]
valid_username_strategy = st.text(
    alphabet=st.sampled_from(USERNAME_VALID_CHARS),
    min_size=USERNAME_MIN_LENGTH,
    max_size=USERNAME_MAX_LENGTH,
)

# Valid email: simple user@host.tld
valid_email_strategy = st.builds(
    lambda local, domain, tld: f"{local}@{domain}.{tld}",
    local=st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=20),
    domain=st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=20),
    tld=st.text(alphabet=string.ascii_lowercase, min_size=2, max_size=6),
).filter(lambda e: _email_meets_spec(e))


# ===========================================================================
# Property 1: Password Validation Correctness
# ===========================================================================


@given(password=valid_password_strategy)
@settings(max_examples=200)
def test_property1_valid_passwords_are_accepted(password: str) -> None:
    """Property 1 (accept path): validator MUST accept any string that satisfies
    the spec (8-128 chars, upper, lower, digit, special).

    **Validates: Requirements 1.3, 1.4**
    """
    assert _password_meets_spec(password), (
        f"Strategy produced a password that fails spec: {password!r}"
    )
    result = validate_password(password)
    assert result == password


@given(password=arbitrary_text_strategy)
@settings(max_examples=200)
def test_property1_invalid_passwords_are_rejected(password: str) -> None:
    """Property 1 (reject path): validator MUST reject any string that violates
    the password spec.

    **Validates: Requirements 1.3, 1.4**
    """
    if _password_meets_spec(password):
        # This input actually satisfies the spec – it must be accepted
        result = validate_password(password)
        assert result == password
    else:
        with pytest.raises(ValueError):
            validate_password(password)


@given(password=st.text(min_size=0, max_size=PASSWORD_MIN_LENGTH - 1))
@settings(max_examples=200)
def test_property1_too_short_rejected(password: str) -> None:
    """Passwords shorter than 8 characters are always rejected.

    **Validates: Requirements 1.4**
    """
    with pytest.raises(ValueError, match="at least"):
        validate_password(password)


@given(
    password=st.text(
        alphabet=string.ascii_letters + string.digits,
        min_size=PASSWORD_MAX_LENGTH + 1,
        max_size=PASSWORD_MAX_LENGTH + 200,
    )
)
@settings(max_examples=200)
def test_property1_too_long_rejected(password: str) -> None:
    """Passwords longer than 128 characters are always rejected.

    **Validates: Requirements 1.4**
    """
    with pytest.raises(ValueError, match="at most"):
        validate_password(password)


# ===========================================================================
# Property 2: Username Validation Correctness
# ===========================================================================


@given(username=valid_username_strategy)
@settings(max_examples=200)
def test_property2_valid_usernames_are_accepted(username: str) -> None:
    """Property 2 (accept path): username validator MUST accept any string
    3-50 chars composed only of [a-zA-Z0-9_-].

    **Validates: Requirements 1.6**
    """
    result = validate_username(username)
    assert result == username


@given(
    username=st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)),
        min_size=0,
        max_size=60,
    )
)
@settings(max_examples=200)
def test_property2_username_iff_condition(username: str) -> None:
    """Property 2 (bidirectional): username validator accepts iff the string
    matches [a-zA-Z0-9_-]{3,50}.

    **Validates: Requirements 1.6**
    """
    if _username_meets_spec(username):
        assert validate_username(username) == username
    else:
        with pytest.raises(ValueError):
            validate_username(username)


@given(username=st.text(min_size=0, max_size=USERNAME_MIN_LENGTH - 1))
@settings(max_examples=200)
def test_property2_username_too_short_rejected(username: str) -> None:
    """Usernames shorter than 3 characters are always rejected.

    **Validates: Requirements 1.6**
    """
    with pytest.raises(ValueError):
        validate_username(username)


@given(
    username=st.text(
        alphabet=st.sampled_from(USERNAME_VALID_CHARS),
        min_size=USERNAME_MAX_LENGTH + 1,
        max_size=USERNAME_MAX_LENGTH + 50,
    )
)
@settings(max_examples=200)
def test_property2_username_too_long_rejected(username: str) -> None:
    """Usernames longer than 50 characters are always rejected.

    **Validates: Requirements 1.6**
    """
    with pytest.raises(ValueError, match="at most"):
        validate_username(username)


# ===========================================================================
# Property 2: Email Validation Correctness
# ===========================================================================


@given(email=valid_email_strategy)
@settings(max_examples=200)
def test_property2_valid_emails_are_accepted(email: str) -> None:
    """Property 2 (accept path): email validator MUST accept any string that
    matches a valid email format and is ≤255 characters.

    **Validates: Requirements 1.6**
    """
    result = validate_email(email)
    assert result == email


@given(
    email=st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)),
        min_size=0,
        max_size=300,
    )
)
@settings(max_examples=200)
def test_property2_email_iff_condition(email: str) -> None:
    """Property 2 (bidirectional): email validator accepts iff the string is a
    valid email format and ≤255 characters.

    **Validates: Requirements 1.6**
    """
    if _email_meets_spec(email):
        assert validate_email(email) == email
    else:
        with pytest.raises(ValueError):
            validate_email(email)


@given(
    extra_length=st.integers(min_value=1, max_value=200),
)
@settings(max_examples=200)
def test_property2_email_exceeding_255_chars_rejected(extra_length: int) -> None:
    """Emails longer than 255 characters are always rejected.

    **Validates: Requirements 1.6**
    """
    # Build a string that exceeds 255 total chars but looks like an email
    # local part padded to make total > 255
    domain = "@b.com"  # 6 chars
    local_length = EMAIL_MAX_LENGTH - len(domain) + extra_length  # guaranteed > 255 total
    over_limit = "a" * local_length + domain
    assert len(over_limit) > EMAIL_MAX_LENGTH
    with pytest.raises(ValueError, match="at most"):
        validate_email(over_limit)


# ===========================================================================
# Property 40: Pydantic Input Length Validation
# ===========================================================================


@given(
    extra_length=st.integers(min_value=1, max_value=500),
)
@settings(max_examples=200)
def test_property40_register_password_exceeding_free_text_limit_rejected(
    extra_length: int,
) -> None:
    """Property 40: RegisterRequest MUST reject a password field exceeding
    10,000 characters with a ValidationError (422 equivalent).

    **Validates: Requirements 18.6**
    """
    long_password = "A" * (MAX_FREE_TEXT_LENGTH + extra_length)
    with pytest.raises(ValidationError):
        RegisterRequest(
            username="validuser",
            email="user@example.com",
            password=long_password,
        )


@given(
    extra_length=st.integers(min_value=1, max_value=200),
)
@settings(max_examples=200)
def test_property40_register_username_exceeding_identifier_limit_rejected(
    extra_length: int,
) -> None:
    """Property 40: RegisterRequest MUST reject a username field exceeding
    255 characters with a ValidationError (422 equivalent).

    **Validates: Requirements 18.6**
    """
    long_username = "a" * (MAX_IDENTIFIER_LENGTH + extra_length)
    with pytest.raises(ValidationError):
        RegisterRequest(
            username=long_username,
            email="user@example.com",
            password="ValidP@ss1",
        )


@given(
    extra_length=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=200)
def test_property40_register_email_exceeding_identifier_limit_rejected(
    extra_length: int,
) -> None:
    """Property 40: RegisterRequest MUST reject an email field exceeding
    255 characters with a ValidationError (422 equivalent).

    **Validates: Requirements 18.6**
    """
    local_part = "a" * (MAX_IDENTIFIER_LENGTH + extra_length - len("@example.com"))
    long_email = local_part + "@example.com"
    assert len(long_email) > MAX_IDENTIFIER_LENGTH
    with pytest.raises(ValidationError):
        RegisterRequest(
            username="validuser",
            email=long_email,
            password="ValidP@ss1",
        )


@given(
    extra_length=st.integers(min_value=1, max_value=200),
)
@settings(max_examples=200)
def test_property40_login_username_exceeding_identifier_limit_rejected(
    extra_length: int,
) -> None:
    """Property 40: LoginRequest MUST reject a username field exceeding
    255 characters with a ValidationError (422 equivalent).

    **Validates: Requirements 18.6**
    """
    long_username = "a" * (MAX_IDENTIFIER_LENGTH + extra_length)
    with pytest.raises(ValidationError):
        LoginRequest(
            username=long_username,
            password="anypassword",
        )


@given(
    extra_length=st.integers(min_value=1, max_value=500),
)
@settings(max_examples=200)
def test_property40_login_password_exceeding_free_text_limit_rejected(
    extra_length: int,
) -> None:
    """Property 40: LoginRequest MUST reject a password field exceeding
    10,000 characters with a ValidationError (422 equivalent).

    **Validates: Requirements 18.6**
    """
    long_password = "A" * (MAX_FREE_TEXT_LENGTH + extra_length)
    with pytest.raises(ValidationError):
        LoginRequest(
            username="validuser",
            password=long_password,
        )
