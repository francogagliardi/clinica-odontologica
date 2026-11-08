"""Builders for C-14 billing integration tests (fictional data only)."""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.comprobantes import ConfiguracionFiscal
from app.models import (
    Comprobante,
    ComprobanteEnvio,
    Paciente,
    SecuenciaComprobante,
)
from tests.integration.caja_helpers import insertar_cobro_db
from tests.integration.cobros_helpers import cobro_payload, hoy_local, setup_cobros
from tests.integration.fiscal_helpers import insertar_comprobante_db
from tests.integration.recursos_helpers import bearer


class FakeRedis:
    """Queue double for enqueue/BRPOP paths (no Redis server needed)."""

    def __init__(
        self,
        *,
        ok: bool = True,
        brpop_error: bool = False,
    ) -> None:
        self.ok = ok
        self.brpop_error = brpop_error
        self.items: list[tuple[str, str]] = []
        self.brpops: int = 0

    async def rpush(self, queue: str, payload: str) -> int:
        if not self.ok:
            raise RuntimeError("redis caído")
        self.items.append((queue, payload))
        return 1

    async def brpop(
        self, queue: str, timeout: int = 0
    ) -> tuple[str, str] | None:
        self.brpops += 1
        if self.brpop_error:
            raise RuntimeError("redis caído")
        for indice, (nombre, payload) in enumerate(self.items):
            if nombre == queue:
                self.items.pop(indice)
                return (nombre, payload)
        return None

    async def aclose(self) -> None:  # para que el worker no falle al cerrar
        return None


def fiscal_config(**overrides: object) -> ConfiguracionFiscal:
    base: dict[str, object] = {
        "cuit": "20000000001",
        "punto_venta": 1,
        "condicion_emisor": "responsable_inscripto",
        "max_intentos": 5,
        "claim_timeout_seconds": 300,
    }
    base.update(overrides)
    return ConfiguracionFiscal(**base)  # type: ignore[arg-type]


async def setup_comprobantes(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Payment fixtures plus today's open register."""
    return await setup_cobros(session_factory, con_caja=True)


def post_cobro(
    api_client,
    data: dict[str, object],
    *,
    actor: str = "recepcionista",
    user_agent: str = "pytest-ua-c14",
    **overrides: object,
):
    return api_client.post(
        "/cobros",
        json=cobro_payload(data, **overrides),
        headers={
            **bearer(data["actores"][actor]),
            "User-Agent": user_agent,
        },
    )


def post_efectivo(
    api_client,
    data: dict[str, object],
    *,
    monto: str = "15000.00",
    actor: str = "recepcionista",
    **overrides: object,
):
    respuesta = post_cobro(
        api_client,
        data,
        actor=actor,
        tipo="otro",
        medio="efectivo",
        monto=monto,
        **overrides,
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


async def leer_comprobante(
    session_factory: async_sessionmaker[AsyncSession],
    comprobante_id: uuid.UUID,
) -> Comprobante | None:
    async with session_factory() as session:
        return await session.get(Comprobante, comprobante_id)


async def comprobante_de_cobro(
    session_factory: async_sessionmaker[AsyncSession],
    cobro_id: uuid.UUID,
) -> Comprobante | None:
    async with session_factory() as session:
        return await session.scalar(
            select(Comprobante).where(Comprobante.cobro_id == cobro_id)
        )


async def comprobantes_del_cobro(
    session_factory: async_sessionmaker[AsyncSession],
    cobro_id: uuid.UUID,
) -> list[Comprobante]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(Comprobante).where(Comprobante.cobro_id == cobro_id)
            )
        )


async def contar_comprobantes(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(
                text("SELECT count(*) FROM comprobantes")
            )
            or 0
        )


async def secuencia_db(
    session_factory: async_sessionmaker[AsyncSession],
    consultorio_id: uuid.UUID,
    punto_venta: int = 1,
) -> SecuenciaComprobante | None:
    async with session_factory() as session:
        return await session.get(
            SecuenciaComprobante, (consultorio_id, punto_venta)
        )


async def envios_de(
    session_factory: async_sessionmaker[AsyncSession],
    comprobante_id: uuid.UUID,
) -> list[ComprobanteEnvio]:
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(ComprobanteEnvio).where(
                    ComprobanteEnvio.comprobante_id == comprobante_id
                )
            )
        )


async def crear_cobro_db(
    session_factory: async_sessionmaker[AsyncSession],
    data: dict[str, object],
    *,
    monto: str = "15000.00",
    estado: str = "aprobado",
) -> uuid.UUID:
    return await insertar_cobro_db(
        session_factory,
        consultorio_id=data["consultorio_id"],
        paciente_id=data["paciente_os_demo"].id,
        tipo="otro",
        medio="efectivo",
        estado=estado,
        monto=monto,
    )


async def crear_comprobante_pendiente(
    session_factory: async_sessionmaker[AsyncSession],
    data: dict[str, object],
    *,
    numero_interno: int = 1,
    punto_venta: int = 1,
    importe: str = "15000.00",
    proximo_intento: datetime | None = None,
    intentos: int = 0,
    estado: str = "pendiente",
) -> uuid.UUID:
    """Insert a payment plus its receipt directly, for worker/API tests."""
    cobro_id = await crear_cobro_db(
        session_factory, data, monto=importe
    )
    return await insertar_comprobante_db(
        session_factory,
        consultorio_id=data["consultorio_id"],
        cobro_id=cobro_id,
        paciente_id=data["paciente_os_demo"].id,
        estado=estado,
        numero_interno=numero_interno,
        punto_venta=punto_venta,
        importe_total=importe,
        proximo_intento=proximo_intento,
        intentos=intentos,
    )


def hoy() -> date:
    return hoy_local()


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def paciente_db(data: dict[str, object]) -> Paciente:
    return data["paciente_os_demo"]


__all__ = [
    "FakeRedis",
    "ahora",
    "comprobante_de_cobro",
    "comprobantes_del_cobro",
    "contar_comprobantes",
    "crear_comprobante_pendiente",
    "crear_cobro_db",
    "envios_de",
    "fiscal_config",
    "hoy",
    "leer_comprobante",
    "paciente_db",
    "post_cobro",
    "post_efectivo",
    "secuencia_db",
    "setup_comprobantes",
]
