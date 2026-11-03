"""Single-use public link tokens (C-03, RN-NO-03).

Only the SHA-256 digest of the token is persisted: a database leak must not
hand over live booking/reminder links. The raw value is returned once to the
caller (inside `IssuedToken`) and never stored.

Errors never embed the raw token, so a log or an error tracker cannot leak a
usable link.
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import TokenUnSoloUso

_TOKEN_BYTES = 32


class TokenError(Exception):
    """Base error for single-use token operations."""


class TokenNotFoundError(TokenError):
    """The given token does not exist (HTTP 404/410 at the API boundary)."""


class TokenAlreadyUsedError(TokenError):
    """The token was already consumed (RN-NO-03: HTTP 410)."""


class TokenExpiredError(TokenError):
    """The token expiration timestamp has passed (HTTP 410)."""


class TokenPurposeError(TokenError):
    """The token exists but belongs to another use case (e.g. reminder vs booking)."""


@dataclass(frozen=True)
class IssuedToken:
    """Raw token (revealed once) plus its persisted, hashed record."""

    token: str
    registro: TokenUnSoloUso


def hash_token(raw_token: str) -> str:
    """SHA-256 digest used as the only stored representation of a token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def create_single_use_token(
    session: AsyncSession,
    tipo: str,
    entidad_tipo: str,
    entidad_id: str,
    expires_minutes: int = 60,
) -> IssuedToken:
    """Generate an opaque 256-bit token and persist only its digest (RN-NO-03)."""
    raw_token = secrets.token_urlsafe(_TOKEN_BYTES)
    now = datetime.now(timezone.utc)

    registro = TokenUnSoloUso(
        id=uuid.uuid4(),
        token_hash=hash_token(raw_token),
        tipo=tipo,
        entidad_tipo=entidad_tipo,
        entidad_id=entidad_id,
        usado=False,
        usado_at=None,
        expira_at=now + timedelta(minutes=expires_minutes),
        created_at=now,
    )
    session.add(registro)
    await session.flush()
    return IssuedToken(token=raw_token, registro=registro)


def _check_purpose(registro: TokenUnSoloUso, expected_tipo: str | None) -> None:
    if expected_tipo is not None and registro.tipo != expected_tipo:
        raise TokenPurposeError(
            "El token no corresponde al propósito solicitado"
        )


async def verify_single_use_token(
    session: AsyncSession,
    raw_token: str,
    expected_tipo: str | None = None,
) -> TokenUnSoloUso:
    """Validate existence, purpose, unused state and expiry without consuming."""
    statement = select(TokenUnSoloUso).where(
        TokenUnSoloUso.token_hash == hash_token(raw_token)
    )
    result = await session.scalars(statement)
    registro = result.first()

    if registro is None:
        raise TokenNotFoundError("Token no encontrado")

    _check_purpose(registro, expected_tipo)

    if registro.usado:
        raise TokenAlreadyUsedError("Token ya utilizado (RN-NO-03)")

    if datetime.now(timezone.utc) > registro.expira_at:
        raise TokenExpiredError("Token expirado")

    return registro


async def consume_single_use_token(
    session: AsyncSession,
    raw_token: str,
    expected_tipo: str | None = None,
) -> TokenUnSoloUso:
    """Atomically consume a token; exactly one concurrent caller can win."""
    now = datetime.now(timezone.utc)
    conditions = [
        TokenUnSoloUso.token_hash == hash_token(raw_token),
        TokenUnSoloUso.usado.is_(False),
        TokenUnSoloUso.expira_at > now,
    ]
    if expected_tipo is not None:
        conditions.append(TokenUnSoloUso.tipo == expected_tipo)

    statement = (
        update(TokenUnSoloUso)
        .where(*conditions)
        .values(usado=True, usado_at=now)
        .returning(TokenUnSoloUso)
    )
    result = await session.scalars(statement)
    consumed = result.first()

    if consumed is not None:
        await session.flush()
        return consumed

    # No row updated: re-read to raise the precise business error.
    return await verify_single_use_token(session, raw_token, expected_tipo)
