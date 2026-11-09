"""Backoffice access management (C-16, design D3/D4/D12).

The API is the authority: the UI only hides what these guards already forbid.
Every endpoint requires an active administrator; responses never include the
password hash. Logout/`me` stay in `auth.py`, and this router is registered
after it so `/usuarios/me` keeps priority over `/usuarios/{id}`.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    client_ip,
    dispositivo,
    get_uow,
    reject_unexpected_query_except,
    require_role,
)
from app.core.security import get_password_hash
from app.domain.acceso import (
    ACCION_USUARIO_ACTIVAR,
    ACCION_USUARIO_CREAR,
    ACCION_USUARIO_DESACTIVAR,
    ACCION_USUARIO_EDITAR,
    ACCION_USUARIO_PASSWORD,
    ACCION_USUARIO_ROLES,
)
from app.infrastructure import audit
from app.infrastructure.uow import UnitOfWork
from app.models.security import Usuario
from app.schemas.usuarios import (
    PasswordUpdate,
    RolResponse,
    RolesUpdate,
    UsuarioCreate,
    UsuarioResponse,
    UsuarioUpdate,
)

router = APIRouter(tags=["usuarios"])

_administrador = require_role("administrador")

_EMAIL_DUPLICADO = "El email ya pertenece a otra cuenta activa"
_SIN_ADMINISTRADOR = (
    "La operación dejaría al sistema sin administrador activo"
)


def _roles_activos(usuario: Usuario) -> list[str]:
    return sorted(
        {
            rol.nombre
            for rol in usuario.roles
            if rol.is_active and rol.deleted_at is None
        }
    )


def _to_response(usuario: Usuario) -> UsuarioResponse:
    return UsuarioResponse(
        id=usuario.id,
        nombre=usuario.nombre,
        email=usuario.email,
        is_active=usuario.is_active,
        roles=_roles_activos(usuario),
    )


async def _get_usuario(uow: UnitOfWork, usuario_id: uuid.UUID) -> Usuario:
    usuario = await uow.usuarios.get(usuario_id)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
    return usuario


async def _resolver_roles(
    uow: UnitOfWork, nombres: list[str]
) -> list[uuid.UUID]:
    roles = await uow.roles.get_by_nombres(nombres)
    if len(roles) != len(set(nombres)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La lista de roles contiene un rol inexistente",
        )
    return [rol.id for rol in roles]


async def _registrar(
    uow: UnitOfWork,
    request: Request,
    current: Usuario,
    accion: str,
    usuario_id: uuid.UUID,
) -> None:
    """Append one audit row inside the same transaction as the mutation."""
    await audit.registrar(
        uow.session,
        accion=accion,
        entidad="usuario",
        entidad_id=usuario_id,
        usuario_id=current.id,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )


@router.get(
    "/usuarios",
    response_model=list[UsuarioResponse],
    summary="Listar cuentas (solo administrador)",
    dependencies=[
        Depends(reject_unexpected_query_except("incluir_inactivos"))
    ],
)
async def list_usuarios(
    _current: Annotated[Usuario, Depends(_administrador)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    incluir_inactivos: Annotated[bool, Query()] = False,
) -> list[UsuarioResponse]:
    usuarios = await uow.usuarios.list_all(
        incluir_inactivos=incluir_inactivos
    )
    return [_to_response(usuario) for usuario in usuarios]


@router.post(
    "/usuarios",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Alta de usuario (solo administrador)",
)
async def create_usuario(
    payload: UsuarioCreate,
    request: Request,
    current: Annotated[Usuario, Depends(_administrador)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> UsuarioResponse:
    if await uow.usuarios.get_by_email(payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_EMAIL_DUPLICADO
        )
    rol_ids = await _resolver_roles(uow, payload.roles)

    usuario = Usuario(
        nombre=payload.nombre,
        email=payload.email,
        hash_password=get_password_hash(payload.password),
    )
    try:
        await uow.usuarios.add(usuario)
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_EMAIL_DUPLICADO
        ) from error
    await uow.usuarios.reemplazar_roles(usuario.id, rol_ids)
    await _registrar(
        uow, request, current, ACCION_USUARIO_CREAR, usuario.id
    )
    return _to_response(usuario)


@router.get(
    "/usuarios/{usuario_id}",
    response_model=UsuarioResponse,
    summary="Detalle de una cuenta (solo administrador)",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def read_usuario(
    usuario_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_administrador)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> UsuarioResponse:
    return _to_response(await _get_usuario(uow, usuario_id))


@router.patch(
    "/usuarios/{usuario_id}",
    response_model=UsuarioResponse,
    summary="Edición parcial, activación y desactivación (solo administrador)",
)
async def update_usuario(
    usuario_id: uuid.UUID,
    payload: UsuarioUpdate,
    request: Request,
    current: Annotated[Usuario, Depends(_administrador)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> UsuarioResponse:
    await uow.usuarios.lock_acceso()
    usuario = await _get_usuario(uow, usuario_id)
    cambios = {
        campo: valor
        for campo, valor in payload.model_dump(exclude_unset=True).items()
        if valor is not None
    }

    if "email" in cambios and cambios["email"] != usuario.email:
        existente = await uow.usuarios.get_by_email(cambios["email"])
        if existente is not None and existente.id != usuario.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_EMAIL_DUPLICADO,
            )

    accion: str | None = None
    desactivado = False
    if "activo" in cambios:
        activo = bool(cambios["activo"])
        if not activo and usuario.id == current.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un administrador no puede desactivar su propia cuenta",
            )
        if not activo and usuario.is_active:
            await uow.usuarios.soft_delete(usuario)
            desactivado = True
            accion = ACCION_USUARIO_DESACTIVAR
        elif activo and not usuario.is_active:
            # The email of a deactivated account may have been reused: reactivar
            # must fail cleanly instead of hitting the partial unique index.
            ocupado = await uow.usuarios.get_by_email(usuario.email)
            if ocupado is not None and ocupado.id != usuario.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=_EMAIL_DUPLICADO,
                )
            try:
                await uow.usuarios.reactivar(usuario)
            except IntegrityError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=_EMAIL_DUPLICADO,
                ) from error
            accion = ACCION_USUARIO_ACTIVAR

    editado = False
    if "nombre" in cambios and cambios["nombre"] != usuario.nombre:
        usuario.nombre = cambios["nombre"]
        editado = True
    if "email" in cambios and cambios["email"] != usuario.email:
        usuario.email = cambios["email"]
        editado = True
    if accion is None and editado:
        accion = ACCION_USUARIO_EDITAR

    try:
        await uow.session.flush()
    except IntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_EMAIL_DUPLICADO
        ) from error

    if desactivado and (
        await uow.usuarios.contar_administradores_activos() == 0
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_SIN_ADMINISTRADOR,
        )
    if accion is not None:
        await _registrar(uow, request, current, accion, usuario.id)
    return _to_response(usuario)


@router.post(
    "/usuarios/{usuario_id}/password",
    response_model=UsuarioResponse,
    summary="Fijar una nueva contraseña (solo administrador)",
)
async def change_password(
    usuario_id: uuid.UUID,
    payload: PasswordUpdate,
    request: Request,
    current: Annotated[Usuario, Depends(_administrador)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> UsuarioResponse:
    usuario = await _get_usuario(uow, usuario_id)
    usuario.hash_password = get_password_hash(payload.password)
    await uow.session.flush()
    await _registrar(
        uow, request, current, ACCION_USUARIO_PASSWORD, usuario.id
    )
    return _to_response(usuario)


@router.get(
    "/roles",
    response_model=list[RolResponse],
    summary="Catálogo fijo de cinco roles (solo administrador)",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def list_roles(
    _current: Annotated[Usuario, Depends(_administrador)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> list[RolResponse]:
    roles = await uow.roles.list_activos()
    return [RolResponse(id=rol.id, nombre=rol.nombre) for rol in roles]


@router.put(
    "/usuarios/{usuario_id}/roles",
    response_model=UsuarioResponse,
    summary="Reemplazar el conjunto de roles (solo administrador)",
)
async def replace_roles(
    usuario_id: uuid.UUID,
    payload: RolesUpdate,
    request: Request,
    current: Annotated[Usuario, Depends(_administrador)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> UsuarioResponse:
    await uow.usuarios.lock_acceso()
    usuario = await _get_usuario(uow, usuario_id)
    rol_ids = await _resolver_roles(uow, payload.roles)
    if set(_roles_activos(usuario)) != set(payload.roles):
        await uow.usuarios.reemplazar_roles(usuario.id, rol_ids)
        if await uow.usuarios.contar_administradores_activos() == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=_SIN_ADMINISTRADOR,
            )
        await _registrar(
            uow, request, current, ACCION_USUARIO_ROLES, usuario.id
        )
    return _to_response(usuario)
