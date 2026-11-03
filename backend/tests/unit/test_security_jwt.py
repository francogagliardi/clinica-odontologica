"""Unit tests for JWT issuance/validation and password hashing (C-03, R-03, DD-07b)."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    normalize_email,
    verify_password,
    verify_password_with_dummy,
)

_SECRET = "test-secret-key-32-bytes-minimum-length!"
_OTHER_SECRET = "different-secret-key-minimum-32-bytes-long!"


def test_password_hash_and_verify() -> None:
    raw = "MiPasswordSeguro123!"
    hashed = get_password_hash(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("OtroPasswordErroneo", hashed) is False


def test_verify_password_with_dummy_never_accepts_missing_hash() -> None:
    # Unknown user: a bcrypt comparison happens but can never succeed.
    assert verify_password_with_dummy("cualquier-password", None) is False
    hashed = get_password_hash("clave-real")
    assert verify_password_with_dummy("clave-real", hashed) is True
    assert verify_password_with_dummy("clave-mala", hashed) is False


def test_normalize_email_trims_and_lowercases() -> None:
    assert normalize_email("  Admin@Clinica.LOCAL ") == "admin@clinica.local"


def test_create_and_decode_access_token() -> None:
    user_id = uuid.uuid4()
    before = datetime.now(timezone.utc)

    token = create_access_token(
        subject=str(user_id),
        secret=_SECRET,
        algorithm="HS256",
        expires_minutes=30,
    )
    assert isinstance(token, str)

    payload = decode_access_token(
        token=token, secret=_SECRET, algorithms=["HS256"]
    )
    assert payload["sub"] == str(user_id)
    assert payload["typ"] == "access"
    assert "exp" in payload and "iat" in payload
    # Roles and email are resolved from PostgreSQL, never trusted from the token.
    assert "roles" not in payload
    assert "email" not in payload
    assert payload["exp"] > int(before.timestamp())


def test_decode_token_with_wrong_type_is_rejected() -> None:
    now = int(datetime.now(timezone.utc).timestamp())
    forged = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "typ": "refresh",
            "iat": now,
            "exp": now + 60,
        },
        _SECRET,
        algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token=forged, secret=_SECRET, algorithms=["HS256"])


def test_decode_unsigned_alg_none_token_is_rejected() -> None:
    now = int(datetime.now(timezone.utc).timestamp())
    unsigned = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "typ": "access",
            "iat": now,
            "exp": now + 60,
        },
        key="",
        algorithm="none",
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token=unsigned, secret=_SECRET, algorithms=["HS256"])


def test_decode_tampered_token_fails() -> None:
    token = create_access_token(
        subject=str(uuid.uuid4()),
        secret=_SECRET,
        algorithm="HS256",
        expires_minutes=30,
    )
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(
            token=token, secret=_OTHER_SECRET, algorithms=["HS256"]
        )


def test_decode_expired_token_fails() -> None:
    token = create_access_token(
        subject=str(uuid.uuid4()),
        secret=_SECRET,
        algorithm="HS256",
        expires_minutes=-5,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token=token, secret=_SECRET, algorithms=["HS256"])


def test_token_missing_required_claim_is_rejected() -> None:
    now = int(datetime.now(timezone.utc).timestamp())
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "iat": now, "exp": now + 60},
        _SECRET,
        algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token=forged, secret=_SECRET, algorithms=["HS256"])
