"""Shared FastAPI dependencies (DI seam, R-02, R-03, RN-SE-01).

C-01 exposes settings access + the strict-boundary guard.
C-03 implements UnitOfWork lifecycle, JWT authentication (`get_current_user`),
and strict RBAC role guards (`require_role`).
"""

import uuid
from collections.abc import AsyncIterator, Callable
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import resources
from app.core.security import decode_access_token
from app.core.settings import Settings, load_settings
from app.core.throttling import LoginRateLimiter, default_login_limiter
from app.infrastructure.uow import UnitOfWork
from app.models.security import Usuario


@lru_cache
def get_settings() -> Settings:
    """Process-cached settings (fail-fast on missing secrets at first use)."""
    return load_settings()


def get_login_limiter() -> LoginRateLimiter:
    """Inject the login throttler (overridable seam for isolated tests)."""
    return default_login_limiter


async def reject_unexpected_query(request: Request) -> None:
    """Strict boundary: baseline GET endpoints declare no params (422 otherwise).

    Enforces the RORO/extra=forbid rule for endpoints without a body: any
    undeclared query field is rejected instead of silently ignored.
    """
    if request.query_params:
        raise HTTPException(
            status_code=422, detail="Unexpected query parameters"
        )


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Retrieve or lazily initialize the application session factory."""
    if resources.session_factory is None:
        settings = get_settings()
        resources.init_resources(settings)
    assert resources.session_factory is not None
    return resources.session_factory


async def get_uow() -> AsyncIterator[UnitOfWork]:
    """Provide a scoped UnitOfWork instance per request."""
    factory = get_session_factory()
    uow = UnitOfWork(factory)
    async with uow:
        yield uow


security_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_bearer)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Usuario:
    """Validate JWT Bearer token and inject active User model (DD-07b)."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Encabezado de autorización ausente o inválido",
        )

    try:
        payload = decode_access_token(
            token=credentials.credentials,
            secret=settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado o con firma adulterada",
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado o inválido",
        )

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado o inválido",
        )

    user = await uow.usuarios.get(user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o inexistente",
        )

    return user


def require_role(*allowed_roles: str) -> Callable[..., Usuario]:
    """RBAC dependency factory checking active user roles (RN-SE-01)."""

    async def role_checker(
        current_user: Annotated[Usuario, Depends(get_current_user)],
    ) -> Usuario:
        user_roles = {
            rol.nombre
            for rol in current_user.roles
            if rol.is_active and rol.deleted_at is None
        }
        if not any(role in user_roles for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes",
            )
        return current_user

    return role_checker
