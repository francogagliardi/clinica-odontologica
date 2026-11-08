"""Exportation endpoints: request, listing, state and ZIP download (C-15).

`POST /exportaciones` only persists the durable job and answers 202; the
worker generates the artifact. Listing/state/download never reveal another
consultorio or another dentist's exportation: those answer 404 without metadata.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError

from app.api.deps import (
    client_ip,
    dispositivo,
    get_consultorio_demo_id,
    get_redis,
    get_uow,
    reject_unexpected_query,
    reject_unexpected_query_except,
    require_role,
)
from app.application.exportaciones import (
    descargar_exportacion,
    obtener_exportacion,
    solicitar_exportacion,
)
from app.infrastructure.uow import UnitOfWork
from app.models.reportes import Exportacion
from app.models.security import Usuario
from app.schemas.exportaciones import (
    ExportacionCreate,
    ExportacionListadoQuery,
    ExportacionResponse,
)

router = APIRouter(prefix="/exportaciones", tags=["exportaciones"])

_exportar = require_role("administrador", "odontologo")


def _to_response(exportacion: Exportacion) -> ExportacionResponse:
    return ExportacionResponse(
        id=exportacion.id,
        consultorio_id=exportacion.consultorio_id,
        solicitado_por=exportacion.solicitado_por,
        alcance=exportacion.alcance,
        paciente_id=exportacion.paciente_id,
        estado=exportacion.estado,
        tamano_bytes=exportacion.tamano_bytes,
        generada_at=exportacion.generada_at,
        ultimo_error=exportacion.ultimo_error,
        intentos=exportacion.intentos,
        created_at=exportacion.created_at,
        updated_at=exportacion.updated_at,
    )


def _es_admin(usuario: Usuario) -> bool:
    return any(
        rol.nombre == "administrador"
        and rol.is_active
        and rol.deleted_at is None
        for rol in usuario.roles
    )


@router.post(
    "",
    response_model=ExportacionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Solicitar una exportación durable (paciente o consultorio)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def create_exportacion(
    payload: ExportacionCreate,
    request: Request,
    current_user: Annotated[Usuario, Depends(_exportar)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    redis_client: Annotated[object | None, Depends(get_redis)],
) -> ExportacionResponse:
    exportacion, _creada = await solicitar_exportacion(
        uow,
        consultorio_id=consultorio_id,
        usuario=current_user,
        alcance=payload.alcance,
        paciente_id=payload.paciente_id,
        redis_client=redis_client,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_response(exportacion)


@router.get(
    "",
    response_model=list[ExportacionResponse],
    summary="Listar exportaciones (el odontólogo solo ve las propias)",
    dependencies=[
        Depends(
            reject_unexpected_query_except("estado", "alcance")
        )
    ],
)
async def list_exportaciones(
    _current: Annotated[Usuario, Depends(_exportar)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    estado: str | None = None,
    alcance: str | None = None,
) -> list[ExportacionResponse]:
    try:
        filtros = ExportacionListadoQuery(
            estado=estado, alcance=alcance
        )
    except ValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error.errors()[0]["msg"],
        ) from error
    exportaciones = await uow.exportaciones.list_filtrado(
        consultorio_id,
        estado=filtros.estado,
        alcance=filtros.alcance,
        solicitado_por=None if _es_admin(_current) else _current.id,
    )
    return [_to_response(exportacion) for exportacion in exportaciones]


@router.get(
    "/{exportacion_id}",
    response_model=ExportacionResponse,
    summary="Estado de una exportación",
    dependencies=[Depends(reject_unexpected_query)],
)
async def read_exportacion(
    exportacion_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_exportar)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> ExportacionResponse:
    return _to_response(
        await obtener_exportacion(
            uow,
            consultorio_id=consultorio_id,
            exportacion_id=exportacion_id,
            usuario=_current,
        )
    )


@router.get(
    "/{exportacion_id}/archivo",
    summary="Descargar el ZIP de una exportación lista",
    dependencies=[Depends(reject_unexpected_query)],
)
async def download_exportacion(
    exportacion_id: uuid.UUID,
    request: Request,
    _current: Annotated[Usuario, Depends(_exportar)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> Response:
    exportacion = await descargar_exportacion(
        uow,
        consultorio_id=consultorio_id,
        exportacion_id=exportacion_id,
        usuario=_current,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    contenido = exportacion.contenido or b""
    return Response(
        content=contenido,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="exportacion-{exportacion.id}.zip"'
            )
        },
    )
