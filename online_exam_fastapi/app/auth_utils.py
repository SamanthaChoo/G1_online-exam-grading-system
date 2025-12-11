"""Authentication utilities: password hashing and token generation."""

import secrets

from passlib.context import CryptContext

# Configure bcrypt to avoid compatibility issues with bcrypt 4.0+
# Use "2b" ident and disable bug detection to prevent 72-byte limit errors
PWD_CONTEXT = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__ident="2b",
    bcrypt__rounds=12,
)


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password for storage."""
    return PWD_CONTEXT.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against its hash."""
    return PWD_CONTEXT.verify(plain_password, password_hash)


def create_reset_token() -> str:
    """Generate a random URL-safe token for password reset."""
    return secrets.token_urlsafe(32)


def generate_otp() -> str:
    """Generate a 6-digit OTP code."""
    return f"{secrets.randbelow(900000) + 100000:06d}"
