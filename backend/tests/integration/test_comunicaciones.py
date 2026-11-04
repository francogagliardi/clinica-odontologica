"""Reminders, workers, endpoints and webhook (C-09)."""

import asyncio
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.application.recordatorios import (
    cancelar_recordatorios,
    procesar_mensaje,
    procesar_reintentos,
    procesar_vencidos,
    programar_recordatorios,
)
from app.application.webhooks import firma_valida, procesar_webhook
from app.infrastructure.uow import UnitOfWork
from app.infrastructure.whatsapp import TestWhatsAppClient
from app.models import MensajeWhatsApp, Recordatorio, RegistroAuditoria, Turno
from app.schemas.comunicaciones import WebhookMensaje
from tests.integration.helpers import run
from tests.integration.recursos_helpers import bearer
from tests.integration.turnos_helpers import (
    insertar_turno_db,
    setup_turnos,
)

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
INICIO = datetime(
    2026, 11, 9, 9, 0, tzinfo=timezone(timedelta(hours=-3))
)


class FakeRedis:
    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []

    async def rpush(self, queue: str, payload: str) -> int:
        self.items.append((queue, payload))
        return 1


class FailClient:
    async def enviar(self, telefono, plantilla, variables) -> str:
        raise RuntimeError("proveedor caído")


def _setup(session_factory) -> dict[str, object]:
    base = run(setup_turnos(session_factory))
    return base


def _turno(
    session_factory, base: dict[str, object], inicio: datetime
) -> uuid.UUID:
    return run(
        insertar_turno_db(
            session_factory,
            consultorio_id=base["consultorio_id"],
            paciente_id=base["paciente"].id,
            profesional_id=base["profesional"].id,
            sillon_id=base["sillon"].id,
            inicio=inicio,
            fin=inicio + timedelta(minutes=60),
        )
    )


def _uow(session_factory):
    return UnitOfWork(session_factory)


async def _recordatorios(session_factory, turno_id: uuid.UUID):
    async with session_factory() as session:
        return list(
            await session.scalars(
                select(Recordatorio).where(Recordatorio.turno_id == turno_id)
            )
        )


def test_programa_48_y_24_y_no_duplica(session_factory) -> None:
    base = _setup(session_factory)
    turno_id = _turno(session_factory, base, INICIO)

    async def programar():
        async with _uow(session_factory) as uow:
            turno = await uow.turnos.get(turno_id)
            assert turno is not None
            await programar_recordatorios(uow, turno, now=NOW)
            await programar_recordatorios(uow, turno, now=NOW)

    run(programar())
    records = run(_recordatorios(session_factory, turno_id))
    assert {record.ventana for record in records} == {"48h", "24h"}
    assert len(records) == 2


def test_turno_cercano_solo_programa_24(session_factory) -> None:
    base = _setup(session_factory)
    turno_id = _turno(session_factory, base, NOW + timedelta(hours=30))

    async def programar():
        async with _uow(session_factory) as uow:
            turno = await uow.turnos.get(turno_id)
            assert turno is not None
            await programar_recordatorios(uow, turno, now=NOW)

    run(programar())
    records = run(_recordatorios(session_factory, turno_id))
    assert {record.ventana for record in records} == {"24h"}


def test_cancelar_recordatorios(session_factory) -> None:
    base = _setup(session_factory)
    turno_id = _turno(session_factory, base, INICIO)

    async def cancelar():
        async with _uow(session_factory) as uow:
            turno = await uow.turnos.get(turno_id)
            assert turno is not None
            await programar_recordatorios(uow, turno, now=NOW)
            await cancelar_recordatorios(uow, turno_id)

    run(cancelar())
    records = run(_recordatorios(session_factory, turno_id))
    assert {record.estado for record in records} == {"cancelado"}


def test_worker_encola_vencido_y_no_futuro(session_factory) -> None:
    base = _setup(session_factory)
    vencido_id = _turno(session_factory, base, NOW + timedelta(hours=50))
    futuro_id = _turno(
        session_factory, base, NOW + timedelta(days=10)
    )
    run(_marcar_vencido(session_factory, vencido_id, NOW - timedelta(minutes=1)))
    run(_marcar_vencido(session_factory, futuro_id, NOW + timedelta(days=1)))
    fake = FakeRedis()

    async def procesar():
        async with _uow(session_factory) as uow:
            return await procesar_vencidos(
                uow,
                fake,
                now=NOW,
                base_url="http://127.0.0.1:8080",
                token_ttl_minutes=10080,
            )

    procesados = run(procesar())
    assert procesados == 1
    assert len(fake.items) == 1
    records = run(_recordatorios(session_factory, vencido_id))
    assert records[0].estado == "encolado"

    async def mensajes():
        async with session_factory() as session:
            return list(await session.scalars(select(MensajeWhatsApp)))

    mensajes_db = run(mensajes())
    assert len(mensajes_db) == 1
    assert mensajes_db[0].payload["variables"]["gestion_url"]


async def _marcar_vencido(session_factory, turno_id, cuando) -> None:
    async with session_factory() as session, session.begin():
        records = list(
            await session.scalars(
                select(Recordatorio).where(
                    Recordatorio.turno_id == turno_id,
                    Recordatorio.ventana == "48h",
                )
            )
        )
        if not records:
            session.add(
                Recordatorio(
                    id=uuid.uuid4(),
                    turno_id=turno_id,
                    ventana="48h",
                    programado_para=cuando,
                    estado="pendiente",
                )
            )
        else:
            for record in records:
                record.programado_para = cuando


def test_dos_workers_no_duplican(session_factory) -> None:
    base = _setup(session_factory)
    turno_id = _turno(session_factory, base, NOW + timedelta(hours=50))
    run(_marcar_vencido(session_factory, turno_id, NOW - timedelta(minutes=1)))
    fake = FakeRedis()

    async def uno():
        async with _uow(session_factory) as uow:
            await procesar_vencidos(
                uow,
                fake,
                now=NOW,
                base_url="http://x",
                token_ttl_minutes=60,
            )

    async def ambos():
        await asyncio.gather(uno(), uno())

    run(ambos())
    async def contar():
        async with session_factory() as session:
            return await session.scalar(
                select(__import__("sqlalchemy").func.count()).select_from(
                    MensajeWhatsApp
                )
            )

    assert run(contar()) == 1


def test_envio_exitoso_y_fallo_con_reintento(session_factory) -> None:
    base = _setup(session_factory)
    turno_id = _turno(session_factory, base, INICIO)
    mensaje_id = run(_mensaje_pendiente(session_factory, turno_id))
    cliente = TestWhatsAppClient()

    async def enviar():
        async with _uow(session_factory) as uow:
            return await procesar_mensaje(
                uow, cliente, mensaje_id, now=NOW, max_intentos=3
            )

    enviado = run(enviar())
    assert enviado is not None and enviado.estado_envio == "enviado"
    assert enviado.proveedor_mensaje_id is not None
    assert len(cliente.enviados) == 1


def test_fallo_agota_intentos_y_audita(session_factory) -> None:
    base = _setup(session_factory)
    turno_id = _turno(session_factory, base, INICIO)
    mensaje_id = run(_mensaje_pendiente(session_factory, turno_id, intentos=2))

    async def enviar():
        async with _uow(session_factory) as uow:
            return await procesar_mensaje(
                uow, FailClient(), mensaje_id, now=NOW, max_intentos=3
            )

    fallido = run(enviar())
    assert fallido is not None and fallido.estado_envio == "fallido"
    assert fallido.intentos == 3

    async def auditoria():
        async with session_factory() as session:
            return await session.scalar(
                select(RegistroAuditoria).where(
                    RegistroAuditoria.accion == "whatsapp_fallo"
                )
            )

    assert run(auditoria()) is not None


async def _mensaje_pendiente(
    session_factory, turno_id: uuid.UUID, intentos: int = 0
) -> uuid.UUID:
    async with session_factory() as session, session.begin():
        mensaje = MensajeWhatsApp(
            turno_id=turno_id,
            plantilla="recordatorio",
            estado_envio="pendiente",
            intentos=intentos,
            payload={"telefono": "+5491100000000", "variables": {}},
        )
        session.add(mensaje)
        await session.flush()
        return mensaje.id


def test_reintento_no_reenvia_enviado(session_factory) -> None:
    base = _setup(session_factory)
    turno_id = _turno(session_factory, base, INICIO)
    mensaje_id = run(_mensaje_pendiente(session_factory, turno_id))
    cliente = TestWhatsAppClient()

    async def dos_veces():
        async with _uow(session_factory) as uow:
            await procesar_mensaje(uow, cliente, mensaje_id, now=NOW)
            await procesar_mensaje(uow, cliente, mensaje_id, now=NOW)

    run(dos_veces())
    assert len(cliente.enviados) == 1


def test_reintentos_vence_backoff(session_factory) -> None:
    base = _setup(session_factory)
    turno_id = _turno(session_factory, base, INICIO)
    mensaje_id = run(_mensaje_pendiente(session_factory, turno_id, intentos=1))

    async def programar():
        async with session_factory() as session, session.begin():
            mensaje = await session.get(MensajeWhatsApp, mensaje_id)
            assert mensaje is not None
            mensaje.proximo_intento = NOW - timedelta(minutes=1)

    run(programar())

    async def reintentar():
        async with _uow(session_factory) as uow:
            return await procesar_reintentos(
                uow, TestWhatsAppClient(), now=NOW
            )

    assert run(reintentar()) == 1


def test_webhook_firma_y_acciones(session_factory, monkeypatch) -> None:
    base = _setup(session_factory)
    turno_id = _turno(session_factory, base, INICIO)
    mensaje_id = run(_mensaje_pendiente(session_factory, turno_id))
    proveedor_id = run(_marcar_enviado(session_factory, mensaje_id))
    secret = "secreto"
    assert firma_valida(b"{}", "sha256=" + "0" * 64, secret) is False

    async def confirmar():
        async with _uow(session_factory) as uow:
            return await procesar_webhook(
                uow,
                [
                    WebhookMensaje(
                        id=proveedor_id, respuesta="confirmar"
                    )
                ],
                now=NOW,
            )

    resultado = run(confirmar())
    assert resultado[0].aplicado is True

    async def estado():
        async with session_factory() as session:
            turno = await session.get(Turno, turno_id)
            return turno.estado if turno else None

    assert run(estado()) == "confirmado"

    duplicado = run(confirmar())
    assert duplicado[0].aplicado is False


async def _marcar_enviado(session_factory, mensaje_id: uuid.UUID) -> str:
    async with session_factory() as session, session.begin():
        mensaje = await session.get(MensajeWhatsApp, mensaje_id)
        assert mensaje is not None
        mensaje.estado_envio = "enviado"
        mensaje.proveedor_mensaje_id = "wamid.test-1"
        return mensaje.proveedor_mensaje_id


def test_webhook_cancelar_y_reprogramar(session_factory) -> None:
    base = _setup(session_factory)
    turno_id = _turno(session_factory, base, INICIO)
    mensaje_id = run(_mensaje_pendiente(session_factory, turno_id))
    proveedor_id = run(_marcar_enviado(session_factory, mensaje_id))

    async def repro():
        async with _uow(session_factory) as uow:
            return await procesar_webhook(
                uow,
                [
                    WebhookMensaje(
                        id=proveedor_id,
                        respuesta="reprogramar",
                        nueva_fecha=INICIO + timedelta(hours=1),
                    )
                ],
                now=NOW,
            )

    assert run(repro())[0].aplicado is True

    async def leer():
        async with session_factory() as session:
            turno = await session.get(Turno, turno_id)
            return turno.inicio if turno else None

    assert run(leer()) == INICIO + timedelta(hours=1)


def test_webhook_pasado_y_desconocido_deriva(session_factory) -> None:
    base = _setup(session_factory)
    turno_id = _turno(session_factory, base, INICIO)
    mensaje_id = run(_mensaje_pendiente(session_factory, turno_id))
    proveedor_id = run(_marcar_enviado(session_factory, mensaje_id))

    async def pasado():
        async with _uow(session_factory) as uow:
            return await procesar_webhook(
                uow,
                [WebhookMensaje(id=proveedor_id, respuesta="confirmar")],
                now=INICIO + timedelta(days=1),
            )

    assert run(pasado())[0].derivado is True

    async def desconocido():
        async with _uow(session_factory) as uow:
            return await procesar_webhook(
                uow,
                [WebhookMensaje(id="wamid.inexistente", respuesta="confirmar")],
                now=NOW,
            )

    assert run(desconocido())[0].derivado is True


def test_endpoints_recordatorios_y_reenvio(api_client, session_factory) -> None:
    base = _setup(session_factory)
    turno_id = _turno(session_factory, base, INICIO)
    mensaje_id = run(_mensaje_pendiente(session_factory, turno_id))
    admin = bearer(base["actores"]["administrador"])
    odontologo = bearer(base["actores"]["odontologo"])

    assert api_client.get(
        "/recordatorios",
        params={"turno_id": str(turno_id)},
        headers=admin,
    ).status_code == 200
    assert api_client.get("/notificaciones", headers=admin).status_code == 200

    reenvio = api_client.post(
        f"/notificaciones/{mensaje_id}/reenviar", headers=admin
    )
    assert reenvio.status_code == 201, reenvio.text
    assert reenvio.json()["id"] != str(mensaje_id)

    assert api_client.post(
        f"/notificaciones/{mensaje_id}/reenviar", headers=odontologo
    ).status_code == 403
    assert api_client.post(
        f"/notificaciones/{uuid.uuid4()}/reenviar", headers=admin
    ).status_code == 404


def test_webhook_endpoint_firma_e_idempotencia(
    api_client, session_factory, monkeypatch
) -> None:
    base = _setup(session_factory)
    turno_id = _turno(session_factory, base, INICIO)
    mensaje_id = run(_mensaje_pendiente(session_factory, turno_id))
    proveedor_id = run(_marcar_enviado(session_factory, mensaje_id))
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "secreto")
    from app.api.deps import get_settings

    get_settings.cache_clear()
    body = json.dumps(
        {"mensajes": [{"id": proveedor_id, "respuesta": "confirmar"}]}
    ).encode()
    firma = hmac.new(b"secreto", body, hashlib.sha256).hexdigest()

    assert api_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"Content-Type": "application/json"},
    ).status_code == 401

    ok = api_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={firma}",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["resultados"][0]["aplicado"] is True

    duplicado = api_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={firma}",
        },
    )
    assert duplicado.status_code == 200
    assert duplicado.json()["resultados"][0]["aplicado"] is False
    get_settings.cache_clear()
