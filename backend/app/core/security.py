"""Security primitives: bcrypt hashing and JWT Bearer signing (C-03, R-01, R-03, DD-07b).

Access tokens carry only the identity (`sub`) plus `typ`, `iat` and `exp`.
Roles and email are deliberately NOT embedded: authorization is always resolved
against PostgreSQL, so a role change takes effect immediately and a stale token
can never grant a permission the user no longer has.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

_ACCESS_TOKEN_TYPE = "access"
_DUMMY_HASH: str | None = None


def normalize_email(email: str) -> str:
    """Canonical email form: trimmed and lower-cased (login is case-insensitive)."""
    return email.strip().lower()


def get_password_hash(password: str) -> str:
    """Hash a clear-text password with bcrypt (salting included)."""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a clear-text password against a stored bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def _get_dummy_hash() -> str:
    """Lazily built bcrypt hash used when the account does not exist.

    Comparing against a real hash keeps the failed-login cost close to the
    valid-account path, so response time does not reveal whether an email is
    registered (user enumeration).
    """
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = get_password_hash("dummy-password-for-timing-only")
    return _DUMMY_HASH


def verify_password_with_dummy(
    plain_password: str, hashed_password: str | None
) -> bool:
    """Verify a password, spending a bcrypt comparison even for unknown users."""
    reference = hashed_password if hashed_password is not None else _get_dummy_hash()
    matched = verify_password(plain_password, reference)
    return matched and hashed_password is not None


def create_access_token(
    subject: str,
    secret: str,
    algorithm: str = "HS256",
    expires_minutes: int = 30,
) -> str:
    """Generate a signed short-lived JWT access token (DD-07b)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=expires_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "typ": _ACCESS_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    encoded_jwt: str = jwt.encode(payload, secret, algorithm=algorithm)
    return encoded_jwt


def decode_access_token(
    token: str,
    secret: str,
    algorithms: list[str] | None = None,
) -> dict[str, Any]:
    """Decode and validate a JWT access token, verifying signature, type and expiry.

    Raises `jwt.PyJWTError` (e.g. `ExpiredSignatureError`, `InvalidSignatureError`,
    `InvalidAlgorithmError`) when the token cannot be trusted.
    """
    if algorithms is None:
        algorithms = ["HS256"]
    payload: dict[str, Any] = jwt.decode(
        token,
        secret,
        algorithms=algorithms,
        options={"require": ["exp", "iat", "sub", "typ"]},
    )
    if payload.get("typ") != _ACCESS_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Unsupported token type")
    return payload


def utcnow_epoch() -> int:
    """Current UTC time as epoch seconds (single source for token clocks)."""
    return int(time.time())
