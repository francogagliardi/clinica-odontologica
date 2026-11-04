"""Authentication endpoints and user identity reads (C-03, R-01, R-02, DD-07b).

Login is audited in `registro_auditoria` (RN-SE-02): successful and failed
attempts are recorded with user (when known), IP and device. The audit row for
a failure is committed **before** raising the 401, because the UnitOfWork rolls
back when the request ends in an exception.

A 429 (throttled) attempt is deliberately not audited: the audit table is
append-only and unthrottled writes there would let an attacker grow it without
bound. That trade-off is documented in the C-03 design.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import (
    client_ip,
    dispositivo,
    get_current_user,
    get_login_limiter,
    get_settings,
    get_uow,
    reject_unexpected_query,
    require_role,
)
from app.core.security import (
    create_access_token,
    normalize_email,
    verify_password_with_dummy,
)
from app.core.settings import Settings
from app.core.throttling import LoginRateLimiter
from app.infrastructure.uow import UnitOfWork
from app.models.security import RegistroAuditoria, Usuario
from app.schemas.auth import LoginRequest, TokenResponse, UsuarioAuthResponse

router = APIRouter(prefix="/usuarios", tags=["auth"])

_MAX_ENTIDAD_ID = 64


def _active_roles(user: Usuario) -> list[str]:
    return sorted(
        {
            rol.nombre
            for rol in user.roles
            if rol.is_active and rol.deleted_at is None
        }
    )


def _to_auth_response(user: Usuario) -> UsuarioAuthResponse:
    return UsuarioAuthResponse(
        id=user.id,
        nombre=user.nombre,
        email=user.email,
        roles=_active_roles(user),
    )


async def _audit(
    uow: UnitOfWork,
    accion: str,
    usuario_id: uuid.UUID | None,
    entidad_id: str,
    ip: str,
    dispositivo: str | None,
) -> None:
    await uow.auditoria.add(
        RegistroAuditoria(
            usuario_id=usuario_id,
            accion=accion,
            entidad="usuario",
            entidad_id=entidad_id[:_MAX_ENTIDAD_ID],
            ip=ip,
            dispositivo=dispositivo,
        )
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión y obtener access token JWT",
)
async def login(
    request: Request,
    payload: LoginRequest,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[LoginRateLimiter, Depends(get_login_limiter)],
) -> TokenResponse:
    """Validate credentials and return a short-lived JWT Bearer token."""
    ip_cliente = client_ip(request)
    agente = dispositivo(request)
    email = normalize_email(payload.email)
    throttle_key = f"{ip_cliente}:{email}"

    if limiter.is_blocked(throttle_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Reintente más tarde.",
            headers={"Retry-After": str(limiter.retry_after(throttle_key))},
        )

    user = await uow.usuarios.get_by_email(email, include_inactive=True)
    password_ok = verify_password_with_dummy(
        payload.password, user.hash_password if user is not None else None
    )

    if (
        not password_ok
        or user is None
        or not user.is_active
        or user.deleted_at is not None
    ):
        limiter.record_failure(throttle_key)
        await _audit(
            uow,
            accion="login_fallido",
            usuario_id=user.id if user is not None else None,
            entidad_id=str(user.id) if user is not None else email,
            ip=ip_cliente,
            dispositivo=agente,
        )
        # Persist the audit before the 401, otherwise the UoW rollback drops it.
        await uow.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    limiter.reset(throttle_key)
    active_roles = _active_roles(user)
    await _audit(
        uow,
        accion="login_exitoso",
        usuario_id=user.id,
        entidad_id=str(user.id),
        ip=ip_cliente,
        dispositivo=agente,
    )

    token = create_access_token(
        subject=str(user.id),
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.jwt_expire_minutes,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
        usuario=UsuarioAuthResponse(
            id=user.id,
            nombre=user.nombre,
            email=user.email,
            roles=active_roles,
        ),
    )


@router.get(
    "/me",
    response_model=UsuarioAuthResponse,
    summary="Datos del usuario autenticado",
    dependencies=[Depends(reject_unexpected_query)],
)
async def read_me(
    current_user: Annotated[Usuario, Depends(get_current_user)],
) -> UsuarioAuthResponse:
    """Return the identity and current roles of the Bearer token owner."""
    return _to_auth_response(current_user)


@router.get(
    "",
    response_model=list[UsuarioAuthResponse],
    summary="Listar usuarios activos (solo administrador)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def list_usuarios(
    _current_admin: Annotated[
        Usuario, Depends(require_role("administrador"))
    ],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> list[UsuarioAuthResponse]:
    """RBAC smoke endpoint: only an administrator reaches this handler."""
    users = await uow.usuarios.list()
    return [_to_auth_response(user) for user in users]
