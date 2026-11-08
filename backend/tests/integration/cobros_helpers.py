"""Builders for C-13 payment API tests (fictional data only)."""

import hashlib
import hmac
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.deps import get_mercadopago_client, get_settings
from app.domain.caja import fecha_local
from app.infrastructure.mercadopago import PagoNormalizado, TestMercadoPagoClient
from app.main import app
from app.models.caja import CajaDiaria, Cobro, MovimientoCaja
from app.models.agenda import Turno
from tests.integration.caja_helpers import insertar_caja_db
from tests.integration.presupuestos_helpers import (
    insertar_presupuesto_db,
    setup_presupuestos,
)
from tests.integration.turnos_helpers import insertar_turno_db

_UA_MP = "pytest-ua-c13"


def hoy_local() -> date:
    return fecha_local(datetime.now(timezone.utc))


def crear_payload(
    *,
    paciente_id: uuid.UUID,
    tipo: str = "otro",
    medio: str = "efectivo",
    monto: str = "15000.00",
    turno_id: uuid.UUID | None = None,
    presupuesto_id: uuid.UUID | None = None,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "paciente_id": str(paciente_id),
        "tipo": tipo,
        "medio": medio,
        "monto": monto,
        "turno_id": str(turno_id) if turno_id else None,
        "presupuesto_id": str(presupuesto_id) if presupuesto_id else None,
    }
    payload.update(overrides)
    return payload


async def setup_cobros(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    con_caja: bool = True,
    con_turnos: bool = True,
) -> dict[str, object]:
    """Clinical/budget fixtures plus the agenda and register C-13 needs."""
    data = await setup_presupuestos(session_factory)
    consultorio_id = data["consultorio_id"]
    actores = data["actores"]
    profesional = data["profesional"]
    sillon = data["sillon"]
    paciente = data["paciente_os_demo"]
    paciente_ajeno = data["paciente_ajeno"]
    endo = data["prestaciones"]["ENDO"]
    cons = data["prestaciones"]["CONS"]
    ahora = datetime.now(timezone.utc)
    base = ahora + timedelta(days=100)

    turnos: dict[str, uuid.UUID] = {}
    if con_turnos:
        turno_sena = await insertar_turno_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            sillon_id=sillon.id,
            prestacion_id=endo.id,
            inicio=base,
            fin=base + timedelta(minutes=90),
            sena_estado="pendiente",
        )
        turno_sin_sena = await insertar_turno_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            sillon_id=sillon.id,
            prestacion_id=cons.id,
            inicio=base + timedelta(days=1),
            fin=base + timedelta(days=1, minutes=30),
            sena_estado="no_requiere",
        )
        turno_sin_prestacion = await insertar_turno_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            sillon_id=sillon.id,
            inicio=base + timedelta(days=2),
            fin=base + timedelta(days=2, minutes=60),
            sena_estado="no_requiere",
        )
        turno_ajeno = await insertar_turno_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_ajeno.id,
            profesional_id=data["profesional_ajeno"].id,
            sillon_id=sillon.id,
            prestacion_id=endo.id,
            inicio=base + timedelta(days=3),
            fin=base + timedelta(days=3, minutes=90),
            sena_estado="pendiente",
        )
        turno_cancelado = await insertar_turno_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            sillon_id=sillon.id,
            prestacion_id=endo.id,
            inicio=base + timedelta(days=4),
            fin=base + timedelta(days=4, minutes=90),
            estado="cancelado",
            sena_estado="pendiente",
        )
        turno_ausente = await insertar_turno_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            sillon_id=sillon.id,
            prestacion_id=endo.id,
            inicio=base + timedelta(days=5),
            fin=base + timedelta(days=5, minutes=90),
            estado="ausente",
            sena_estado="pendiente",
        )
        turnos = {
            "sena": turno_sena,
            "sin_sena": turno_sin_sena,
            "sin_prestacion": turno_sin_prestacion,
            "ajeno": turno_ajeno,
            "cancelado": turno_cancelado,
            "ausente": turno_ausente,
        }

    presupuesto_id = await insertar_presupuesto_db(
        session_factory,
        consultorio_id=consultorio_id,
        paciente_id=paciente.id,
        profesional_id=profesional.id,
        creado_por=actores["administrador"].id,
        estado="aceptado",
        subtotal="50000.00",
        cobertura_calculada="0.00",
        copago="50000.00",
    )
    presupuesto_ajeno = await insertar_presupuesto_db(
        session_factory,
        consultorio_id=consultorio_id,
        paciente_id=paciente_ajeno.id,
        profesional_id=data["profesional_ajeno"].id,
        creado_por=actores["administrador"].id,
        estado="aceptado",
        subtotal="30000.00",
        cobertura_calculada="0.00",
        copago="30000.00",
    )

    caja_id: uuid.UUID | None = None
    if con_caja:
        caja_id = await insertar_caja_db(
            session_factory,
            consultorio_id=consultorio_id,
            fecha=hoy_local(),
            monto_apertura="10000.00",
        )

    return {
        **data,
        "turnos_cobro": turnos,
        "presupuesto_cobro": presupuesto_id,
        "presupuesto_ajeno_cobro": presupuesto_ajeno,
        "caja_id": caja_id,
        "hoy": hoy_local(),
        "ahora": ahora,
        "endo": endo,
        "cons": cons,
    }


def cobro_payload(
    data: dict[str, object], *, actor: str = "administrador", **overrides
) -> dict[str, object]:
    base = {
        "paciente_id": data["paciente_os_demo"].id,
        "tipo": "otro",
        "medio": "efectivo",
        "monto": "15000.00",
    }
    base.update(overrides)
    return crear_payload(**base)


@contextmanager
def mp_override(
    cliente: TestMercadoPagoClient | object,
) -> Iterator[object]:
    """Share one provider instance between POST /cobros and the webhook."""
    app.dependency_overrides[get_mercadopago_client] = lambda: cliente
    try:
        yield cliente
    finally:
        app.dependency_overrides.pop(get_mercadopago_client, None)


def pago(
    *,
    cobro_id: uuid.UUID,
    monto: str = "10000.00",
    estado: str = "aprobado",
    pago_id: str = "mp-pago-1",
    moneda: str = "ARS",
) -> PagoNormalizado:
    return PagoNormalizado(
        proveedor_pago_id=pago_id,
        cobro_id=cobro_id,
        estado=estado,
        monto=Decimal(monto),
        moneda=moneda,
        fecha=datetime.now(timezone.utc),
    )


def firma_mp(
    pago_id: str,
    *,
    request_id: str = "req-c13",
    secret: str | None = None,
    ts: int | None = None,
) -> dict[str, str]:
    secreto = secret or get_settings().mp_webhook_secret
    timestamp = ts or int(datetime.now(timezone.utc).timestamp())
    manifest = f"id:{pago_id};request-id:{request_id};ts:{timestamp};"
    digest = hmac.new(
        secreto.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return {
        "x-signature": f"ts={timestamp},v1={digest}",
        "x-request-id": request_id,
        "user-agent": _UA_MP,
    }


def webhook_payload(pago_id: str) -> dict[str, object]:
    return {
        "type": "payment",
        "action": "payment.updated",
        "data": {"id": pago_id},
    }


async def leer_cobro(
    session_factory: async_sessionmaker[AsyncSession], cobro_id: uuid.UUID
) -> Cobro | None:
    async with session_factory() as session:
        return await session.get(Cobro, cobro_id)


async def leer_turno(
    session_factory: async_sessionmaker[AsyncSession], turno_id: uuid.UUID
) -> Turno | None:
    async with session_factory() as session:
        return await session.get(Turno, turno_id)


async def movimientos_de(
    session_factory: async_sessionmaker[AsyncSession], cobro_id: uuid.UUID
) -> list[MovimientoCaja]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(MovimientoCaja).where(
                    MovimientoCaja.cobro_id == cobro_id
                )
            )
        )


async def cajas_hoy(
    session_factory: async_sessionmaker[AsyncSession],
    consultorio_id: uuid.UUID,
) -> list[CajaDiaria]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(CajaDiaria).where(
                    CajaDiaria.consultorio_id == consultorio_id,
                    CajaDiaria.fecha == hoy_local(),
                )
            )
        )


async def cerrar_caja_db(
    session_factory: async_sessionmaker[AsyncSession],
    consultorio_id: uuid.UUID,
    usuario_id: uuid.UUID,
) -> None:
    async with session_factory() as session, session.begin():
        caja = await session.scalar(
            select(CajaDiaria).where(
                CajaDiaria.consultorio_id == consultorio_id,
                CajaDiaria.fecha == hoy_local(),
            )
        )
        assert caja is not None
        caja.estado = "cerrada"
        caja.monto_sistema_efectivo = caja.monto_apertura
        caja.monto_contado = caja.monto_apertura
        caja.diferencia = Decimal("0.00")
        caja.cerrada_por = usuario_id
        caja.cerrada_at = datetime.now(timezone.utc)


async def setear_cobro(
    session_factory: async_sessionmaker[AsyncSession],
    cobro_id: uuid.UUID,
    *,
    estado: str | None = None,
    proveedor_pago_id: str | None = None,
) -> None:
    async with session_factory() as session, session.begin():
        cobro = await session.get(Cobro, cobro_id)
        assert cobro is not None
        if estado is not None:
            cobro.estado = estado
        if proveedor_pago_id is not None:
            cobro.proveedor_pago_id = proveedor_pago_id
