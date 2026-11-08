"""Insurance agreements and their local coverage rules (C-05, DD-11)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import (
    get_cobertura_provider,
    get_consultorio_demo_id,
    get_uow,
    reject_unexpected_query,
    reject_unexpected_query_except,
    require_role,
)
from app.application.cobertura import validar_cobertura
from app.application.presupuestos import CoberturaProvider
from app.infrastructure.uow import UnitOfWork
from app.models.comercial import ObraSocial
from app.models.security import Usuario
from app.schemas.cobertura import CoberturaResponse
from app.schemas.pacientes import (
    ObraSocialCreate,
    ObraSocialResponse,
    ObraSocialUpdate,
    ReglasCobertura,
)

router = APIRouter(prefix="/obras-sociales", tags=["obras-sociales"])

_lectura = require_role(
    "administrador", "odontologo", "recepcionista", "auditor"
)
_escritura = require_role("administrador", "recepcionista")
_alta_baja = require_role("administrador")


def _to_response(obra_social: ObraSocial) -> ObraSocialResponse:
    return ObraSocialResponse(
        id=obra_social.id,
        consultorio_id=obra_social.consultorio_id,
        nombre=obra_social.nombre,
        nomenclador_ref=obra_social.nomenclador_ref,
        reglas_cobertura=ReglasCobertura(**obra_social.reglas_cobertura),
        validacion_externa=obra_social.validacion_externa,
        is_active=obra_social.is_active,
    )


async def _activa(
    uow: UnitOfWork, consultorio_id: uuid.UUID, obra_social_id: uuid.UUID
) -> ObraSocial:
    obra_social = await uow.obras_sociales.get(obra_social_id)
    if (
        obra_social is None
        or obra_social.consultorio_id != consultorio_id
        or not obra_social.is_active
        or obra_social.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Obra social no encontrada",
        )
    return obra_social


async def _validar_nombre(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    nombre: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    if (
        await uow.obras_sociales.get_by_nombre(
            consultorio_id, nombre, exclude_id
        )
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una obra social activa con ese nombre",
        )


async def _validar_reglas(
    uow: UnitOfWork, reglas: ReglasCobertura
) -> None:
    """Reject codes outside the active catalogue before persisting (D8)."""
    if not reglas.prestaciones_cubiertas:
        return
    activos = await uow.prestaciones.codigos_activos(
        reglas.prestaciones_cubiertas
    )
    desconocidos = sorted(set(reglas.prestaciones_cubiertas) - activos)
    if desconocidos:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Códigos fuera del catálogo activo: "
                + ", ".join(desconocidos)
            ),
        )


@router.get(
    "",
    response_model=list[ObraSocialResponse],
    summary="Listar obras sociales activas",
    dependencies=[Depends(reject_unexpected_query)],
)
async def list_obras_sociales(
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> list[ObraSocialResponse]:
    obras = await uow.obras_sociales.list_by_consultorio(consultorio_id)
    return [_to_response(obra) for obra in obras]


@router.get(
    "/cobertura",
    response_model=CoberturaResponse,
    summary="Validar cobertura de una práctica (solo reglas locales)",
    dependencies=[
        Depends(
            reject_unexpected_query_except("paciente_id", "prestacion_id")
        )
    ],
)
async def cobertura(
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
    paciente_id: uuid.UUID,
    prestacion_id: uuid.UUID,
    provider: Annotated[
        CoberturaProvider, Depends(get_cobertura_provider)
    ],
) -> CoberturaResponse:
    paciente, prestacion, resultado = await validar_cobertura(
        uow,
        provider,
        consultorio_id=consultorio_id,
        paciente_id=paciente_id,
        prestacion_id=prestacion_id,
    )
    return CoberturaResponse(
        paciente_id=paciente.id,
        prestacion_id=prestacion.id,
        estado=resultado.estado,  # type: ignore[arg-type]
        cobertura_porcentaje=resultado.cobertura_porcentaje,
        cobertura_monto=resultado.cobertura_monto,
        copago_monto=resultado.copago_monto,
    )


@router.post(
    "",
    response_model=ObraSocialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear obra social (solo administrador)",
)
async def create_obra_social(
    payload: ObraSocialCreate,
    _current: Annotated[Usuario, Depends(_alta_baja)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> ObraSocialResponse:
    await _validar_nombre(uow, consultorio_id, payload.nombre)
    await _validar_reglas(uow, payload.reglas_cobertura)
    obra_social = ObraSocial(
        consultorio_id=consultorio_id,
        nombre=payload.nombre,
        nomenclador_ref=payload.nomenclador_ref,
        reglas_cobertura=payload.reglas_cobertura.model_dump(),
        validacion_externa=payload.validacion_externa,
    )
    await uow.obras_sociales.add(obra_social)
    return _to_response(obra_social)


@router.get(
    "/{obra_social_id}",
    response_model=ObraSocialResponse,
    summary="Obtener una obra social activa",
    dependencies=[Depends(reject_unexpected_query)],
)
async def read_obra_social(
    obra_social_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> ObraSocialResponse:
    return _to_response(
        await _activa(uow, consultorio_id, obra_social_id)
    )


@router.put(
    "/{obra_social_id}",
    response_model=ObraSocialResponse,
    summary="Editar obra social (administrador o recepción)",
)
async def update_obra_social(
    obra_social_id: uuid.UUID,
    payload: ObraSocialUpdate,
    _current: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> ObraSocialResponse:
    obra_social = await _activa(uow, consultorio_id, obra_social_id)
    await _validar_nombre(
        uow, consultorio_id, payload.nombre, exclude_id=obra_social.id
    )
    await _validar_reglas(uow, payload.reglas_cobertura)
    obra_social.nombre = payload.nombre
    obra_social.nomenclador_ref = payload.nomenclador_ref
    obra_social.reglas_cobertura = payload.reglas_cobertura.model_dump()
    obra_social.validacion_externa = payload.validacion_externa
    await uow.session.flush()
    return _to_response(obra_social)


@router.delete(
    "/{obra_social_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Baja lógica de obra social (solo administrador)",
)
async def delete_obra_social(
    obra_social_id: uuid.UUID,
    _current: Annotated[Usuario, Depends(_alta_baja)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> Response:
    obra_social = await _activa(uow, consultorio_id, obra_social_id)
    await uow.obras_sociales.soft_delete(obra_social)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
