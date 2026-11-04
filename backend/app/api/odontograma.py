"""Odontogram endpoints: FDI findings over immutable snapshots (C-11 slice 3).

Every valid finding creates a complete new version: the current snapshot is
copied except the changed tooth/face, and the new state is inserted. The old
snapshots remain untouched and are protected by PostgreSQL triggers. The
history row is locked (`FOR UPDATE`) so concurrent writes serialize and never
reuse a version number (design D6).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    client_ip,
    dispositivo,
    get_consultorio_demo_id,
    get_uow,
    reject_unexpected_query_except,
    require_role,
)
from app.application.clinica import (
    ROLES_LECTURA,
    auditar,
    crear_version_odontograma,
    puede_escribir_historia,
    puede_leer_historia,
)
from app.infrastructure.uow import UnitOfWork
from app.models.clinica import (
    HallazgoDental,
    HistoriaClinica,
    Odontograma,
)
from app.models.security import Usuario
from app.schemas.clinica import (
    HallazgoCreate,
    HallazgoResponse,
    OdontogramaResponse,
)

router = APIRouter(tags=["odontograma"])

_lectura = require_role(*ROLES_LECTURA)
_escritura = require_role("odontologo")

_HISTORIA_NO_ENCONTRADA = "Historia clínica no encontrada"
_NO_ACCESO = "No tenés acceso clínico a este paciente"


def _to_hallazgo(hallazgo: HallazgoDental) -> HallazgoResponse:
    return HallazgoResponse(
        id=hallazgo.id,
        pieza=hallazgo.pieza,
        cara=hallazgo.cara,
        estado=hallazgo.estado,
        diagnostico=hallazgo.diagnostico,
        cie10=hallazgo.cie10,
        fecha=hallazgo.fecha,
    )


async def _historia_activa(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    historia_id: uuid.UUID,
) -> HistoriaClinica:
    historia = await uow.historias.get(historia_id)
    if (
        historia is None
        or historia.consultorio_id != consultorio_id
        or historia.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_HISTORIA_NO_ENCONTRADA,
        )
    return historia


async def _exigir_lectura(
    uow: UnitOfWork, usuario: Usuario, paciente_id: uuid.UUID
) -> None:
    if not await puede_leer_historia(uow, usuario, paciente_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=_NO_ACCESO
        )


async def _exigir_escritura(
    uow: UnitOfWork, usuario: Usuario, paciente_id: uuid.UUID
) -> None:
    if not await puede_escribir_historia(uow, usuario, paciente_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=_NO_ACCESO
        )


def _es_conflicto_de_version(error: IntegrityError) -> bool:
    original = getattr(error, "orig", error)
    sqlstate = getattr(original, "sqlstate", None) or getattr(
        original, "pgcode", None
    )
    return sqlstate == "23505"


async def _snapshot_response(
    uow: UnitOfWork, odontograma: Odontograma | None
) -> OdontogramaResponse:
    if odontograma is None:
        return OdontogramaResponse(version=None, hallazgos=[])
    hallazgos = await uow.hallazgos.list_by_odontograma(odontograma.id)
    return OdontogramaResponse(
        version=odontograma.version,
        hallazgos=[_to_hallazgo(hallazgo) for hallazgo in hallazgos],
    )


@router.get(
    "/historia-clinica/{historia_id}/odontograma",
    response_model=OdontogramaResponse,
    summary="Leer la versión vigente del odontograma",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def read_odontograma(
    historia_id: uuid.UUID,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> OdontogramaResponse:
    historia = await _historia_activa(uow, consultorio_id, historia_id)
    await _exigir_lectura(uow, current_user, historia.paciente_id)
    return await _snapshot_response(
        uow, await uow.odontogramas.get_vigente(historia.id)
    )


@router.get(
    "/historia-clinica/{historia_id}/odontograma/versiones/{version}",
    response_model=OdontogramaResponse,
    summary="Leer una versión histórica del odontograma",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def read_odontograma_version(
    historia_id: uuid.UUID,
    version: int,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> OdontogramaResponse:
    historia = await _historia_activa(uow, consultorio_id, historia_id)
    await _exigir_lectura(uow, current_user, historia.paciente_id)
    odontograma = await uow.odontogramas.get_por_version(
        historia.id, version
    )
    if odontograma is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Versión de odontograma no encontrada",
        )
    return await _snapshot_response(uow, odontograma)


@router.post(
    "/historia-clinica/{historia_id}/odontograma/hallazgos",
    response_model=OdontogramaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un hallazgo creando una versión nueva",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def create_hallazgo(
    historia_id: uuid.UUID,
    payload: HallazgoCreate,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> OdontogramaResponse:
    historia = await _historia_activa(uow, consultorio_id, historia_id)
    await _exigir_escritura(uow, current_user, historia.paciente_id)

    try:
        odontograma = await crear_version_odontograma(
            uow,
            historia_id=historia.id,
            pieza=payload.pieza,
            cara=payload.cara,
            estado=payload.estado,
            diagnostico=payload.diagnostico,
            cie10=payload.cie10,
            fecha=payload.fecha,
        )
    except IntegrityError as error:
        if _es_conflicto_de_version(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Otra escritura creó la misma versión; reintentá",
            ) from error
        raise

    await auditar(
        uow,
        accion="odontograma.versionar",
        entidad="odontograma",
        entidad_id=odontograma.id,
        usuario_id=current_user.id,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return await _snapshot_response(uow, odontograma)


@router.get(
    "/odontograma/hallazgos/{hallazgo_id}",
    response_model=HallazgoResponse,
    summary="Leer un hallazgo (PUT/DELETE no existen: 405)",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def read_hallazgo(
    hallazgo_id: uuid.UUID,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> HallazgoResponse:
    hallazgo = await uow.hallazgos.get(hallazgo_id)
    if hallazgo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hallazgo no encontrado",
        )
    odontograma = await uow.odontogramas.get(hallazgo.odontograma_id)
    if odontograma is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hallazgo no encontrado",
        )
    historia = await uow.historias.get(odontograma.historia_id)
    if (
        historia is None
        or historia.consultorio_id != consultorio_id
        or historia.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hallazgo no encontrado",
        )
    await _exigir_lectura(uow, current_user, historia.paciente_id)
    return _to_hallazgo(hallazgo)
