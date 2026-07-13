"""Authentication request/response schemas and validators.

Provides Pydantic models for auth endpoints and standalone validation
functions for password, username, and email fields.
"""

import re

from pydantic import BaseModel, field_validator

# Max lengths
MAX_IDENTIFIER_LENGTH = 255
MAX_FREE_TEXT_LENGTH = 10_000

# Password constraints
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
PASSWORD_SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

# Username constraints
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 50
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,50}$")

# Email constraints
EMAIL_MAX_LENGTH = 255
EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)


def validate_password(password: str) -> str:
    """Validate password meets strength requirements.

    Requirements:
    - 8 to 128 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character from: !@#$%^&*()_+-=[]{}|;:,.<>?

    Args:
        password: The password string to validate.

    Returns:
        The password if valid.

    Raises:
        ValueError: If password does not meet requirements.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
        )
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"Password must be at most {PASSWORD_MAX_LENGTH} characters long"
        )
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*()_+=\[\]{}|;:,.<>?\-]", password):
        raise ValueError(
            "Password must contain at least one special character from: "
            "!@#$%^&*()_+-=[]{}|;:,.<>?"
        )
    return password


def validate_username(username: str) -> str:
    """Validate username format.

    Requirements:
    - 3 to 50 characters
    - Only alphanumeric characters, underscores, and hyphens

    Args:
        username: The username string to validate.

    Returns:
        The username if valid.

    Raises:
        ValueError: If username does not meet requirements.
    """
    if len(username) < USERNAME_MIN_LENGTH:
        raise ValueError(
            f"Username must be at least {USERNAME_MIN_LENGTH} characters long"
        )
    if len(username) > USERNAME_MAX_LENGTH:
        raise ValueError(
            f"Username must be at most {USERNAME_MAX_LENGTH} characters long"
        )
    if not USERNAME_PATTERN.match(username):
        raise ValueError(
            "Username must contain only alphanumeric characters, underscores, and hyphens"
        )
    return username


def validate_email(email: str) -> str:
    """Validate email format.

    Requirements:
    - Valid email format (user@domain.tld)
    - Maximum 255 characters

    Args:
        email: The email string to validate.

    Returns:
        The email if valid.

    Raises:
        ValueError: If email does not meet requirements.
    """
    if len(email) > EMAIL_MAX_LENGTH:
        raise ValueError(
            f"Email must be at most {EMAIL_MAX_LENGTH} characters long"
        )
    if not EMAIL_PATTERN.match(email):
        raise ValueError("Email must be a valid email address format")
    return email


class RegisterRequest(BaseModel):
    """Registration request schema."""

    username: str
    email: str
    password: str

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        if len(v) > MAX_IDENTIFIER_LENGTH:
            raise ValueError(
                f"Username must be at most {MAX_IDENTIFIER_LENGTH} characters"
            )
        return validate_username(v)

    @field_validator("email")
    @classmethod
    def check_email(cls, v: str) -> str:
        if len(v) > MAX_IDENTIFIER_LENGTH:
            raise ValueError(
                f"Email must be at most {MAX_IDENTIFIER_LENGTH} characters"
            )
        return validate_email(v)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if len(v) > MAX_FREE_TEXT_LENGTH:
            raise ValueError(
                f"Password must be at most {MAX_FREE_TEXT_LENGTH} characters"
            )
        return validate_password(v)


class LoginRequest(BaseModel):
    """Login request schema."""

    username: str
    password: str

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        if len(v) > MAX_IDENTIFIER_LENGTH:
            raise ValueError(
                f"Username must be at most {MAX_IDENTIFIER_LENGTH} characters"
            )
        return v

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if len(v) > MAX_FREE_TEXT_LENGTH:
            raise ValueError(
                f"Password must be at most {MAX_FREE_TEXT_LENGTH} characters"
            )
        return v


class TokenPair(BaseModel):
    """JWT token pair response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900


class UserResponse(BaseModel):
    """User response schema (public user data)."""

    id: int
    username: str
    email: str
