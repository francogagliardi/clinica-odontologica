"""Shared builders for the offer lifecycle tests (C-10 slice 3)."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.domain.agenda import ARGENTINA_OFFSET
from app.models import (
    EntradaListaEspera,
    MensajeWhatsApp,
    RegistroAuditoria,
)
from tests.integration.helpers import run
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.recursos_helpers import bearer
from tests.integration.turnos_helpers import (
    prestacion_id,
    setup_turnos,
    turno_payload,
)

FECHA = "2026-11-09"


class FakeRedis:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.items: list[tuple[str, str]] = []

    async def rpush(self, queue: str, payload: str) -> int:
        if not self.ok:
            raise RuntimeError("redis caído")
        self.items.append((queue, payload))
        return 1


def hora(hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 11, 9, hora, minuto, tzinfo=ARGENTINA_OFFSET)


def setup_base(session_factory) -> dict[str, object]:
    base = run(setup_turnos(session_factory))
    base["cons"] = run(prestacion_id(session_factory, "CONS"))
    base["endo"] = run(prestacion_id(session_factory, "ENDO"))
    base["paciente2"] = run(
        create_paciente(
            session_factory,
            base["consultorio_id"],
            nombre="Bruno",
            apellido="Oferta",
            dni="42111223",
            telefono="+5491100000012",
        )
    )
    base["paciente3"] = run(
        create_paciente(
            session_factory,
            base["consultorio_id"],
            nombre="Carla",
            apellido="Oferta",
            dni="42111224",
            telefono="+5491100000013",
        )
    )
    return base


def crear_entrada(
    api_client,
    base,
    *,
    paciente=None,
    prestacion=None,
    profesional=None,
) -> dict[str, object]:
    response = api_client.post(
        "/lista-espera",
        json={
            "paciente_id": str((paciente or base["paciente"]).id),
            "prestacion_id": str(prestacion or base["cons"]),
            "profesional_id": (
                str(profesional.id) if profesional is not None else None
            ),
        },
        headers=bearer(base["actores"]["recepcionista"]),
    )
    assert response.status_code == 201, response.text
    return response.json()


def crear_turno(api_client, base, *, prestacion=None, **overrides):
    payload = turno_payload(
        paciente_id=base["paciente"].id,
        profesional_id=base["profesional"].id,
        sillon_id=base["sillon"].id,
        prestacion_id=prestacion if prestacion is not None else base["cons"],
        **overrides,
    )
    response = api_client.post(
        "/turnos",
        json=payload,
        headers=bearer(base["actores"]["recepcionista"]),
    )
    assert response.status_code == 201, response.text
    return response.json()


def cancelar(api_client, base, turno_id) -> int:
    return api_client.patch(
        f"/turnos/{turno_id}/estado",
        json={"estado": "cancelado"},
        headers=bearer(base["actores"]["recepcionista"]),
    ).status_code


def reservar_publico(api_client, base, **overrides):
    payload = {
        "nombre": "Publico",
        "apellido": "Paralelo",
        "dni": "43666777",
        "telefono": "11 5555-6666",
        "email": "paralelo@example.test",
        "profesional_id": str(base["profesional"].id),
        "prestacion_id": str(base["cons"]),
        "inicio": hora(9).isoformat(),
    }
    payload.update(overrides)
    return api_client.post("/reservar/demo/turnos", json=payload)


def leer_entrada(session_factory, entrada_id) -> EntradaListaEspera:
    async def leer():
        async with session_factory() as session:
            entrada = await session.get(
                EntradaListaEspera, uuid.UUID(str(entrada_id))
            )
            assert entrada is not None
            return entrada

    return run(leer())


def mensajes_oferta(session_factory) -> list[MensajeWhatsApp]:
    async def leer():
        async with session_factory() as session:
            return list(
                await session.scalars(
                    select(MensajeWhatsApp)
                    .where(MensajeWhatsApp.plantilla == "oferta_hueco")
                    .order_by(MensajeWhatsApp.created_at)
                )
            )

    return run(leer())


def token_de(mensaje: MensajeWhatsApp) -> str:
    return str(mensaje.payload["variables"]["oferta_url"]).rsplit("/", 1)[-1]


def contar_auditoria(
    session_factory, accion: str, entidad_id=None
) -> int:
    async def contar() -> int:
        async with session_factory() as session:
            statement = select(func.count()).select_from(RegistroAuditoria)
            statement = statement.where(RegistroAuditoria.accion == accion)
            if entidad_id is not None:
                statement = statement.where(
                    RegistroAuditoria.entidad_id == str(entidad_id)
                )
            return await session.scalar(statement)

    return run(contar())


def forzar_expiracion(session_factory, entrada_id, cuando: datetime) -> None:
    async def expirar() -> None:
        async with session_factory() as session, session.begin():
            entrada = await session.get(
                EntradaListaEspera, uuid.UUID(str(entrada_id))
            )
            assert entrada is not None
            entrada.oferta_expira_en = cuando

    run(expirar())


def marcar_mensaje_enviado(
    session_factory, mensaje_id, proveedor_id: str
) -> None:
    async def marcar() -> None:
        async with session_factory() as session, session.begin():
            mensaje = await session.get(
                MensajeWhatsApp, uuid.UUID(str(mensaje_id))
            )
            assert mensaje is not None
            mensaje.estado_envio = "enviado"
            mensaje.proveedor_mensaje_id = proveedor_id

    run(marcar())


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def en_minutos(minutos: int) -> datetime:
    return ahora() + timedelta(minutes=minutos)
