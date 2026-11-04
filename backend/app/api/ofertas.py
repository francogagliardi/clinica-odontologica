"""Public offer links: consult, accept and reject (C-10, D6/D8/D12).

No JWT here: authorization is the single-use `oferta_hueco` token (RN-NO-03).
Acceptance converts the offer into an appointment in the retained professional,
chair and interval; a lost slot answers 409 after committing the state change.
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.api.deps import get_redis, get_settings, get_uow, reject_unexpected_query
from app.application.lista_espera import (
    OfertaInvalida,
    OfertaPerdida,
    OfertaVencida,
    aceptar_oferta,
    rechazar_oferta,
)
from app.core.settings import Settings
from app.domain.agenda import ARGENTINA_OFFSET
from app.infrastructure.tokens import TokenError, verify_single_use_token
from app.infrastructure.uow import UnitOfWork
from app.schemas.lista_espera import (
    OfertaAceptadaResponse,
    OfertaPublicaResponse,
    OfertaRechazoResponse,
    PrestacionOfertaPublica,
    ProfesionalOfertaPublico,
)
from app.schemas.publico import SenaPublica

router = APIRouter(prefix="/reservar/oferta", tags=["reservar"])

_SLOT_PERDIDO = "El horario ya fue ocupado por otra reserva"


def _invalida() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="La oferta no es válida o venció",
    )


@router.get(
    "/{token}",
    response_model=OfertaPublicaResponse,
    summary="Consultar una oferta de hueco liberado sin consumir el token",
    dependencies=[Depends(reject_unexpected_query)],
)
async def consultar_oferta(
    token: str,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> OfertaPublicaResponse:
    try:
        registro = await verify_single_use_token(
            uow.session, token, expected_tipo="oferta_hueco"
        )
    except TokenError as error:
        raise _invalida() from error

    try:
        entrada_id = uuid.UUID(registro.entidad_id)
    except ValueError as error:
        raise _invalida() from error

    entrada = await uow.lista_espera.get(entrada_id)
    if (
        entrada is None
        or entrada.deleted_at is not None
        or entrada.estado != "ofrecido"
        or entrada.oferta_expira_en is None
        or entrada.oferta_expira_en <= datetime.now(timezone.utc)
        or entrada.oferta_inicio is None
        or entrada.oferta_fin is None
        or entrada.oferta_profesional_id is None
    ):
        raise _invalida()

    prestacion = await uow.prestaciones.get(entrada.prestacion_id)
    profesional = await uow.profesionales.get(entrada.oferta_profesional_id)
    if prestacion is None or profesional is None:  # pragma: no cover - parity
        raise _invalida()

    return OfertaPublicaResponse(
        prestacion=PrestacionOfertaPublica(
            id=prestacion.id,
            codigo=prestacion.codigo,
            nombre=prestacion.nombre,
            duracion_min=prestacion.duracion_min,
        ),
        profesional=ProfesionalOfertaPublico(
            id=profesional.id,
            matricula=profesional.matricula,
            especialidades=profesional.especialidades,
        ),
        inicio=entrada.oferta_inicio.astimezone(ARGENTINA_OFFSET),
        fin=entrada.oferta_fin.astimezone(ARGENTINA_OFFSET),
        vence_en=entrada.oferta_expira_en.astimezone(ARGENTINA_OFFSET),
    )


@router.post(
    "/{token}/aceptar",
    response_model=OfertaAceptadaResponse,
    summary="Aceptar la oferta y convertirla en turno",
    responses={
        409: {"description": "El horario ya fue ocupado por otra reserva"},
        410: {"description": "Token inválido, vencido o ya usado"},
    },
)
async def aceptar(
    token: str,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    redis_client: Annotated[object | None, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OfertaAceptadaResponse | JSONResponse:
    try:
        resultado = await aceptar_oferta(
            uow,
            token,
            base_url=settings.app_base_url,
            ttl_minutos=settings.lista_espera_oferta_ttl_minutos,
            redis_client=redis_client,
        )
    except (OfertaInvalida, OfertaVencida) as error:
        raise _invalida() from error

    if isinstance(resultado, OfertaPerdida):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": _SLOT_PERDIDO},
        )

    turno = resultado.turno
    prestacion = (
        await uow.prestaciones.get(turno.prestacion_id)
        if turno.prestacion_id is not None
        else None
    )
    return OfertaAceptadaResponse(
        turno_id=turno.id,
        inicio=turno.inicio.astimezone(ARGENTINA_OFFSET),
        fin=turno.fin.astimezone(ARGENTINA_OFFSET),
        estado=turno.estado,
        sena=SenaPublica(
            requiere=prestacion.requiere_sena if prestacion else False,
            monto=prestacion.monto_sena if prestacion else None,
            estado=turno.sena_estado,
        ),
    )


@router.post(
    "/{token}/rechazar",
    response_model=OfertaRechazoResponse,
    summary="Rechazar la oferta y liberar el hueco",
    responses={410: {"description": "Token inválido, vencido o ya usado"}},
)
async def rechazar(
    token: str,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    redis_client: Annotated[object | None, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OfertaRechazoResponse:
    try:
        await rechazar_oferta(
            uow,
            token,
            base_url=settings.app_base_url,
            ttl_minutos=settings.lista_espera_oferta_ttl_minutos,
            redis_client=redis_client,
        )
    except (OfertaInvalida, OfertaVencida) as error:
        raise _invalida() from error
    return OfertaRechazoResponse(estado="vencido")
