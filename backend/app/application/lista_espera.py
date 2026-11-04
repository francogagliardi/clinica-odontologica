"""Waiting-list offer lifecycle: signal, retention, expiry and conversion.

Design D1: `registrar_hueco_liberado` is the single trigger invoked by the
three cancellation paths (reception, public link and WhatsApp webhook). It
writes the `hueco_liberado` audit record exactly once and, in the same
transaction, claims the oldest compatible entry and retains the freed interval
for it.

Design D3/D4: the FIFO order is the `orden` identity column; the claim uses
`FOR UPDATE SKIP LOCKED`, and the retention lives in a SAVEPOINT so an
exclusion violation (23P01) or a deadlock between the two partial GiST
constraints (40P01) is translated into "slot already retained" instead of
aborting the cancellation.

Design D5/D6: the sweep claims expired offers with an atomic UPDATE that also
clears the retention in the same statement, then rotates the freed interval to
the next compatible entry if it is still free. Acceptance and rejection consume
the token first, then lock the entry; a lost slot commits the consumption and
returns an explicit result so the caller can answer 409 without undoing it.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError

from app.application.ofertas_hueco import emitir_oferta
from app.application.turnos import ComandoTurno, crear_turno
from app.infrastructure.tokens import TokenError, consume_single_use_token
from app.infrastructure.uow import UnitOfWork
from app.models.agenda import Turno
from app.models.lista_espera import EntradaListaEspera
from app.models.security import RegistroAuditoria
from app.models.token import TokenUnSoloUso

_CONFLICTOS_DE_RETENCION = frozenset({"23P01", "40P01"})
_CONFLICTOS_DE_CONVERSION = frozenset(
    {status.HTTP_404_NOT_FOUND, status.HTTP_409_CONFLICT}
)


class OfertaInvalida(Exception):
    """The token is unknown, used, expired or of another purpose (HTTP 410)."""


class OfertaVencida(Exception):
    """The token was consumed but the offer is no longer usable (HTTP 410)."""


@dataclass(frozen=True)
class Hueco:
    """Freed interval with the resources that must be offered together."""

    consultorio_id: uuid.UUID
    prestacion_id: uuid.UUID
    profesional_id: uuid.UUID
    sillon_id: uuid.UUID
    inicio: datetime
    fin: datetime


@dataclass(frozen=True)
class OfertaAceptada:
    """The offer became an appointment."""

    turno: Turno


@dataclass(frozen=True)
class OfertaPerdida:
    """Another booking took the interval: the entry expired and (maybe) rotated."""


def _sqlstate(error: BaseException) -> str | None:
    original = getattr(error, "orig", error)
    return getattr(original, "sqlstate", None) or getattr(
        original, "pgcode", None
    )


def _momento(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _hueco_de_turno(turno: Turno) -> Hueco | None:
    if turno.prestacion_id is None:
        return None
    return Hueco(
        consultorio_id=turno.consultorio_id,
        prestacion_id=turno.prestacion_id,
        profesional_id=turno.profesional_id,
        sillon_id=turno.sillon_id,
        inicio=turno.inicio,
        fin=turno.fin,
    )


def _hueco_de_entrada(entrada: EntradaListaEspera) -> Hueco | None:
    if (
        entrada.oferta_profesional_id is None
        or entrada.oferta_sillon_id is None
        or entrada.oferta_inicio is None
        or entrada.oferta_fin is None
    ):
        return None
    return Hueco(
        consultorio_id=entrada.consultorio_id,
        prestacion_id=entrada.prestacion_id,
        profesional_id=entrada.oferta_profesional_id,
        sillon_id=entrada.oferta_sillon_id,
        inicio=entrada.oferta_inicio,
        fin=entrada.oferta_fin,
    )


def oferta_vigente(
    entrada: EntradaListaEspera | None, now: datetime
) -> bool:
    """Lazy expiry: `oferta_expira_en == now` already counts as expired (D5)."""
    return (
        entrada is not None
        and entrada.deleted_at is None
        and entrada.estado == "ofrecido"
        and entrada.oferta_expira_en is not None
        and entrada.oferta_expira_en > now
    )


async def registrar_hueco_liberado(
    uow: UnitOfWork,
    turno: Turno,
    *,
    now: datetime | None = None,
    base_url: str = "",
    ttl_minutos: int = 30,
    redis_client: object | None = None,
) -> EntradaListaEspera | None:
    """Audit the freed slot once and offer it to the waiting list (D1).

    Called *after* the cancellation has set the terminal state and before the
    UnitOfWork commits, so the audit, the retention and the message share the
    cancellation transaction.
    """
    momento = _momento(now)
    uow.session.add(
        RegistroAuditoria(
            accion="hueco_liberado",
            entidad="turno",
            entidad_id=str(turno.id),
        )
    )
    await uow.session.flush()
    hueco = _hueco_de_turno(turno)
    if hueco is None:
        # Without a service there is no compatible entry to filter by.
        return None
    return await ofrecer_hueco(
        uow,
        hueco,
        now=momento,
        base_url=base_url,
        ttl_minutos=ttl_minutos,
        redis_client=redis_client,
    )


async def ofrecer_hueco(
    uow: UnitOfWork,
    hueco: Hueco,
    *,
    now: datetime | None = None,
    base_url: str = "",
    ttl_minutos: int = 30,
    redis_client: object | None = None,
) -> EntradaListaEspera | None:
    """Retain the interval for the first compatible entry and offer it.

    Returns the offered entry, or None when there is no compatible candidate or
    the interval is already retained by another live offer.
    """
    momento = _momento(now)
    entrada = await uow.lista_espera.siguiente_pendiente_compatible(
        consultorio_id=hueco.consultorio_id,
        prestacion_id=hueco.prestacion_id,
        profesional_id=hueco.profesional_id,
    )
    if entrada is None:
        return None
    if not await _retener(uow, entrada, hueco, momento, ttl_minutos):
        return None
    await emitir_oferta(
        uow,
        entrada,
        now=momento,
        base_url=base_url,
        ttl_minutos=ttl_minutos,
        redis_client=redis_client,
    )
    return entrada


async def procesar_ofertas_vencidas(
    uow: UnitOfWork,
    redis_client,
    *,
    now: datetime | None = None,
    base_url: str = "",
    ttl_minutos: int = 30,
) -> int:
    """Expire due offers and rotate each freed interval to the next entry (D5).

    The claim is an atomic `UPDATE ... RETURNING` that clears the retention in
    the same statement (the CHECK forbids a non-`ofrecido` row from holding
    one), so the GiST index releases the slot before rotating.
    """
    momento = _momento(now)
    candidatas = await uow.lista_espera.list_ofertas_vencidas(momento)
    procesadas = 0
    for candidata in candidatas:
        hueco = _hueco_de_entrada(candidata)
        reclamada = await uow.session.scalar(
            update(EntradaListaEspera)
            .where(
                EntradaListaEspera.id == candidata.id,
                EntradaListaEspera.estado == "ofrecido",
                EntradaListaEspera.oferta_expira_en <= momento,
            )
            .values(**_datos_vencida())
            .returning(EntradaListaEspera.id)
            .execution_options(synchronize_session=False)
        )
        if reclamada is None:
            continue
        candidata_id = candidata.id
        uow.session.expire(candidata)
        await uow.session.flush()
        uow.session.add(
            RegistroAuditoria(
                accion="oferta_hueco_vencida",
                entidad="entrada_lista_espera",
                entidad_id=str(candidata_id),
            )
        )
        await uow.session.flush()
        procesadas += 1
        await _rotar(
            uow,
            hueco,
            now=momento,
            base_url=base_url,
            ttl_minutos=ttl_minutos,
            redis_client=redis_client,
        )
    return procesadas


async def aceptar_oferta(
    uow: UnitOfWork,
    token: str,
    *,
    now: datetime | None = None,
    base_url: str = "",
    ttl_minutos: int = 30,
    redis_client: object | None = None,
) -> OfertaAceptada | OfertaPerdida:
    """Accept an offer from its single-use link (D6).

    The token is consumed first; if the offer is no longer usable the
    consumption is committed before raising `OfertaVencida`, so the same link
    cannot be retried forever on a lost slot.
    """
    momento = _momento(now)
    registro = await _consumir_token(uow, token)
    entrada = await _entrada_del_registro(uow, registro)
    if (
        entrada is None
        or entrada.deleted_at is not None
        or entrada.estado != "ofrecido"
    ):
        await uow.commit()
        raise OfertaVencida("La oferta ya no está disponible")

    hueco = _hueco_de_entrada(entrada)
    if not oferta_vigente(entrada, momento):
        if hueco is not None and not await _rango_libre(uow, hueco, momento):
            return await _perder(
                uow,
                entrada,
                now=momento,
                base_url=base_url,
                ttl_minutos=ttl_minutos,
                redis_client=redis_client,
            )
        await uow.commit()
        raise OfertaVencida("La oferta venció")

    return await _convertir(
        uow,
        entrada,
        now=momento,
        base_url=base_url,
        ttl_minutos=ttl_minutos,
        redis_client=redis_client,
    )


async def aceptar_entrada(
    uow: UnitOfWork,
    entrada: EntradaListaEspera,
    *,
    now: datetime | None = None,
    base_url: str = "",
    ttl_minutos: int = 30,
    redis_client: object | None = None,
) -> OfertaAceptada | OfertaPerdida:
    """Convert a live offer already locked by the caller (webhook path)."""
    return await _convertir(
        uow,
        entrada,
        now=_momento(now),
        base_url=base_url,
        ttl_minutos=ttl_minutos,
        redis_client=redis_client,
    )


async def rechazar_oferta(
    uow: UnitOfWork,
    token: str,
    *,
    now: datetime | None = None,
    base_url: str = "",
    ttl_minutos: int = 30,
    redis_client: object | None = None,
) -> EntradaListaEspera:
    """Reject an offer from its link: release, mark `vencido` and rotate."""
    momento = _momento(now)
    registro = await _consumir_token(uow, token)
    entrada = await _entrada_del_registro(uow, registro)
    if not oferta_vigente(entrada, momento):
        raise OfertaVencida("La oferta ya no está disponible")
    assert entrada is not None
    await rechazar_entrada(
        uow,
        entrada,
        now=momento,
        base_url=base_url,
        ttl_minutos=ttl_minutos,
        redis_client=redis_client,
    )
    return entrada


async def rechazar_entrada(
    uow: UnitOfWork,
    entrada: EntradaListaEspera,
    *,
    now: datetime | None = None,
    base_url: str = "",
    ttl_minutos: int = 30,
    redis_client: object | None = None,
) -> None:
    """Release a live offer already locked by the caller (webhook path)."""
    momento = _momento(now)
    hueco = _hueco_de_entrada(entrada)
    await _marcar_vencida(uow, entrada, "oferta_hueco_rechazada")
    await _rotar(
        uow,
        hueco,
        now=momento,
        base_url=base_url,
        ttl_minutos=ttl_minutos,
        redis_client=redis_client,
    )


def _datos_vencida() -> dict[str, object]:
    """Values of a released retention: the CHECK forbids keeping it (D2)."""
    return {
        "estado": "vencido",
        "oferta_profesional_id": None,
        "oferta_sillon_id": None,
        "oferta_inicio": None,
        "oferta_fin": None,
        "oferta_expira_en": None,
    }


async def _consumir_token(
    uow: UnitOfWork, token: str
) -> TokenUnSoloUso:
    try:
        return await consume_single_use_token(
            uow.session, token, expected_tipo="oferta_hueco"
        )
    except TokenError as error:
        raise OfertaInvalida(str(error)) from error


async def _entrada_del_registro(
    uow: UnitOfWork, registro: TokenUnSoloUso
) -> EntradaListaEspera | None:
    try:
        entrada_id = uuid.UUID(registro.entidad_id)
    except ValueError:
        return None
    return await uow.lista_espera.get_for_update(entrada_id)


async def _retener(
    uow: UnitOfWork,
    entrada: EntradaListaEspera,
    hueco: Hueco,
    now: datetime,
    ttl_minutos: int,
) -> bool:
    """Write the retention in a savepoint; False when it is already taken."""
    try:
        async with uow.session.begin_nested():
            entrada.estado = "ofrecido"
            entrada.oferta_profesional_id = hueco.profesional_id
            entrada.oferta_sillon_id = hueco.sillon_id
            entrada.oferta_inicio = hueco.inicio
            entrada.oferta_fin = hueco.fin
            entrada.oferta_expira_en = now + timedelta(minutes=ttl_minutos)
            await uow.session.flush()
    except DBAPIError as error:
        if _sqlstate(error) in _CONFLICTOS_DE_RETENCION:
            return False
        raise
    return True


async def _convertir(
    uow: UnitOfWork,
    entrada: EntradaListaEspera,
    *,
    now: datetime,
    base_url: str,
    ttl_minutos: int,
    redis_client: object | None,
) -> OfertaAceptada | OfertaPerdida:
    hueco = _hueco_de_entrada(entrada)
    if hueco is None:  # pragma: no cover - CHECK guarantees a full offer
        await uow.commit()
        raise OfertaVencida("La oferta no tiene recursos retenidos")
    try:
        async with uow.session.begin_nested():
            turno = await crear_turno(
                uow,
                entrada.consultorio_id,
                ComandoTurno(
                    paciente_id=entrada.paciente_id,
                    profesional_id=hueco.profesional_id,
                    sillon_id=hueco.sillon_id,
                    prestacion_id=entrada.prestacion_id,
                    inicio=hueco.inicio,
                    origen="online",
                    es_sobreturno=False,
                    color_sobreturno=None,
                ),
                retencion_excluida=entrada.id,
            )
    except HTTPException as error:
        if error.status_code not in _CONFLICTOS_DE_CONVERSION:
            raise
        return await _perder(
            uow,
            entrada,
            now=now,
            base_url=base_url,
            ttl_minutos=ttl_minutos,
            redis_client=redis_client,
        )
    except DBAPIError as error:
        if _sqlstate(error) not in _CONFLICTOS_DE_RETENCION:
            raise
        return await _perder(
            uow,
            entrada,
            now=now,
            base_url=base_url,
            ttl_minutos=ttl_minutos,
            redis_client=redis_client,
        )

    entrada.estado = "convertido"
    entrada.turno_id = turno.id
    _limpiar_retencion(entrada)
    await uow.session.flush()
    return OfertaAceptada(turno=turno)


async def _perder(
    uow: UnitOfWork,
    entrada: EntradaListaEspera,
    *,
    now: datetime,
    base_url: str,
    ttl_minutos: int,
    redis_client: object | None,
) -> OfertaPerdida:
    hueco = _hueco_de_entrada(entrada)
    await _marcar_vencida(uow, entrada, "oferta_hueco_perdida")
    await _rotar(
        uow,
        hueco,
        now=now,
        base_url=base_url,
        ttl_minutos=ttl_minutos,
        redis_client=redis_client,
    )
    return OfertaPerdida()


async def _marcar_vencida(
    uow: UnitOfWork, entrada: EntradaListaEspera, accion: str
) -> None:
    entrada.estado = "vencido"
    _limpiar_retencion(entrada)
    await uow.session.flush()
    uow.session.add(
        RegistroAuditoria(
            accion=accion,
            entidad="entrada_lista_espera",
            entidad_id=str(entrada.id),
        )
    )
    await uow.session.flush()


def _limpiar_retencion(entrada: EntradaListaEspera) -> None:
    entrada.oferta_profesional_id = None
    entrada.oferta_sillon_id = None
    entrada.oferta_inicio = None
    entrada.oferta_fin = None
    entrada.oferta_expira_en = None


async def _rango_libre(
    uow: UnitOfWork, hueco: Hueco, now: datetime
) -> bool:
    """No active appointment and no other live offer occupies the interval."""
    solapados = await uow.turnos.list_solapados(
        consultorio_id=hueco.consultorio_id,
        profesional_id=hueco.profesional_id,
        sillon_id=hueco.sillon_id,
        inicio=hueco.inicio,
        fin=hueco.fin,
    )
    if solapados:
        return False
    retenciones = await uow.lista_espera.retenciones_vigentes(
        profesional_id=hueco.profesional_id,
        sillon_id=hueco.sillon_id,
        desde=hueco.inicio,
        hasta=hueco.fin,
        now=now,
    )
    return not retenciones


async def _rotar(
    uow: UnitOfWork,
    hueco: Hueco | None,
    *,
    now: datetime,
    base_url: str,
    ttl_minutos: int,
    redis_client: object | None,
) -> EntradaListaEspera | None:
    """Offer the interval to the next entry only if it is still free (D5)."""
    if hueco is None:
        return None
    if not await _rango_libre(uow, hueco, now):
        return None
    return await ofrecer_hueco(
        uow,
        hueco,
        now=now,
        base_url=base_url,
        ttl_minutos=ttl_minutos,
        redis_client=redis_client,
    )
