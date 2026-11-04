"""Freed-slot trigger, FIFO offer, message/token and public offer query (C-10).

Tasks 4.1 and 5.1 (red first): the three cancellations must emit
`hueco_liberado` once, retain the freed interval for the first compatible entry,
persist the WhatsApp offer message, issue the `oferta_hueco` token and enqueue it,
all without breaking the cancellation when Redis is down.
"""

import hashlib
import hmac
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.api.deps import get_redis, get_settings
from app.domain.agenda import ARGENTINA_OFFSET
from app.infrastructure.tokens import consume_single_use_token, hash_token
from app.main import app
from app.models import (
    EntradaListaEspera,
    MensajeWhatsApp,
    RegistroAuditoria,
    TokenUnSoloUso,
)
from tests.integration.helpers import run
from tests.integration.lista_espera_helpers import vencer_entrada
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.recursos_helpers import bearer, create_profesional
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


def _hora(hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 11, 9, hora, minuto, tzinfo=ARGENTINA_OFFSET)


def _setup(session_factory) -> dict[str, object]:
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
    return base


def _entrada(
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


def _turno(api_client, base, prestacion=None, **overrides) -> dict[str, object]:
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


def _cancelar(api_client, base, turno_id) -> int:
    return api_client.patch(
        f"/turnos/{turno_id}/estado",
        json={"estado": "cancelado"},
        headers=bearer(base["actores"]["recepcionista"]),
    ).status_code


def _usar_redis(fake: FakeRedis) -> None:
    app.dependency_overrides[get_redis] = lambda: fake


def _leer_entrada(session_factory, entrada_id) -> EntradaListaEspera:
    async def leer():
        async with session_factory() as session:
            entrada = await session.get(
                EntradaListaEspera, uuid.UUID(str(entrada_id))
            )
            assert entrada is not None
            return entrada

    return run(leer())


def _contar_auditoria(session_factory, accion: str, entidad_id) -> int:
    from sqlalchemy import func

    async def contar() -> int:
        async with session_factory() as session:
            return await session.scalar(
                select(func.count())
                .select_from(RegistroAuditoria)
                .where(
                    RegistroAuditoria.accion == accion,
                    RegistroAuditoria.entidad_id == str(entidad_id),
                )
            )

    return run(contar())


def _mensajes_oferta(session_factory) -> list[MensajeWhatsApp]:
    async def leer():
        async with session_factory() as session:
            return list(
                await session.scalars(
                    select(MensajeWhatsApp).where(
                        MensajeWhatsApp.plantilla == "oferta_hueco"
                    )
                )
            )

    return run(leer())


def _token_de(mensaje: MensajeWhatsApp) -> str:
    url = str(mensaje.payload["variables"]["oferta_url"])
    return url.rsplit("/", 1)[-1]


def _mensaje_recordatorio(
    session_factory, turno_id, proveedor_id: str
) -> None:
    async def insertar() -> None:
        async with session_factory() as session, session.begin():
            session.add(
                MensajeWhatsApp(
                    turno_id=turno_id,
                    plantilla="recordatorio",
                    estado_envio="enviado",
                    proveedor_mensaje_id=proveedor_id,
                    payload={
                        "telefono": "+5491100000012",
                        "variables": {},
                    },
                )
            )

    run(insertar())


# --- Disparo del hueco liberado ---------------------------------------------


def test_patch_cancelado_retiene_audita_y_encola(
    api_client, session_factory
) -> None:
    """Expected: reception cancellation triggers the whole offer chain once."""
    base = _setup(session_factory)
    entrada = _entrada(api_client, base)
    turno = _turno(api_client, base)
    fake = FakeRedis()
    _usar_redis(fake)

    assert _cancelar(api_client, base, turno["id"]) == 200

    assert _contar_auditoria(
        session_factory, "hueco_liberado", turno["id"]
    ) == 1
    retenida = _leer_entrada(session_factory, entrada["id"])
    assert retenida.estado == "ofrecido"
    assert retenida.oferta_profesional_id == base["profesional"].id
    assert retenida.oferta_sillon_id == base["sillon"].id
    assert retenida.oferta_inicio == _hora(9)
    assert retenida.oferta_fin == _hora(9, 30)
    assert retenida.oferta_expira_en > datetime.now(timezone.utc)

    mensajes = _mensajes_oferta(session_factory)
    assert len(mensajes) == 1
    mensaje = mensajes[0]
    assert mensaje.lista_espera_id == retenida.id
    assert mensaje.turno_id is None
    assert mensaje.estado_envio == "pendiente"
    assert mensaje.payload["telefono"] == base["paciente"].telefono
    variables = mensaje.payload["variables"]
    assert variables["paciente"] == "Turno Demo"
    assert variables["fecha"] == "09/11/2026"
    assert variables["hora"] == "09:00"
    assert variables["matricula"] == base["profesional"].matricula
    assert variables["oferta_url"].endswith(
        f"/reservar/oferta/{_token_de(mensaje)}"
    )
    assert fake.items == [("whatsapp:send", str(mensaje.id))]


def test_cancelacion_por_enlace_publico_retiene_y_audita(
    api_client, session_factory
) -> None:
    """Expected: the management link cancellation triggers the same service."""
    base = _setup(session_factory)
    reserva = api_client.post(
        "/reservar/demo/turnos",
        json={
            "nombre": "Link",
            "apellido": "Publico",
            "dni": "43555444",
            "telefono": "11 4444-6666",
            "email": "link.oferta@example.test",
            "profesional_id": str(base["profesional"].id),
            "prestacion_id": str(base["cons"]),
            "inicio": _hora(9).isoformat(),
        },
    )
    assert reserva.status_code == 201, reserva.text
    token = reserva.json()["gestion_url"].rsplit("/", 1)[-1]
    entrada = _entrada(api_client, base)

    cancelacion = api_client.post(f"/reservar/gestion/{token}/cancelar")
    assert cancelacion.status_code == 200, cancelacion.text

    assert (
        _contar_auditoria(
            session_factory, "hueco_liberado", reserva.json()["turno_id"]
        )
        == 1
    )
    assert (
        _leer_entrada(session_factory, entrada["id"]).estado == "ofrecido"
    )
    assert len(_mensajes_oferta(session_factory)) == 1


def test_webhook_cancelar_retiene_y_no_duplica_la_auditoria(
    api_client, session_factory, monkeypatch
) -> None:
    """Expected: the webhook uses the shared service, so the trace is unique."""
    base = _setup(session_factory)
    turno = _turno(api_client, base)
    _mensaje_recordatorio(session_factory, turno["id"], "wamid.c10-1")
    entrada = _entrada(api_client, base)

    monkeypatch.setenv("WHATSAPP_APP_SECRET", "secreto")
    get_settings.cache_clear()
    body = json.dumps(
        {"mensajes": [{"id": "wamid.c10-1", "respuesta": "cancelar"}]}
    ).encode()
    firma = hmac.new(b"secreto", body, hashlib.sha256).hexdigest()

    respuesta = api_client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={firma}",
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultados"][0]["aplicado"] is True

    assert (
        _contar_auditoria(session_factory, "hueco_liberado", turno["id"]) == 1
    )
    assert (
        _leer_entrada(session_factory, entrada["id"]).estado == "ofrecido"
    )
    assert len(_mensajes_oferta(session_factory)) == 1
    get_settings.cache_clear()


# --- FIFO -------------------------------------------------------------------


def test_fifo_gana_la_entrada_de_menor_orden(api_client, session_factory) -> None:
    """Expected: only the oldest compatible entry is offered."""
    base = _setup(session_factory)
    primera = _entrada(api_client, base)
    segunda = _entrada(
        api_client, base, paciente=base["paciente2"]
    )
    turno = _turno(api_client, base)
    _usar_redis(FakeRedis())

    assert _cancelar(api_client, base, turno["id"]) == 200

    assert _leer_entrada(session_factory, primera["id"]).estado == "ofrecido"
    assert _leer_entrada(session_factory, segunda["id"]).estado == "pendiente"
    mensajes = _mensajes_oferta(session_factory)
    assert len(mensajes) == 1
    assert mensajes[0].lista_espera_id == uuid.UUID(primera["id"])


def test_fifo_saltea_la_entrada_incompatible_y_usa_los_recursos_liberados(
    api_client, session_factory
) -> None:
    """Expected: fixed professional mismatch is skipped; the next one takes it."""
    base = _setup(session_factory)
    otro_profesional = run(
        create_profesional(
            session_factory, base["consultorio_id"], "MP-OFERTA-OTRO"
        )
    )
    incompatibles = _entrada(
        api_client, base, profesional=otro_profesional
    )
    compatible = _entrada(
        api_client, base, paciente=base["paciente2"]
    )
    turno = _turno(api_client, base)
    _usar_redis(FakeRedis())

    assert _cancelar(api_client, base, turno["id"]) == 200

    assert (
        _leer_entrada(session_factory, incompatibles["id"]).estado
        == "pendiente"
    )
    retenida = _leer_entrada(session_factory, compatible["id"])
    assert retenida.estado == "ofrecido"
    assert retenida.oferta_profesional_id == base["profesional"].id
    assert retenida.oferta_sillon_id == base["sillon"].id
    assert retenida.oferta_inicio == _hora(9)
    assert retenida.oferta_fin == _hora(9, 30)


def test_sin_candidatas_no_retiene_ni_mensajea_ni_encola(
    api_client, session_factory
) -> None:
    """Edge: a service mismatch leaves the freed slot untouched."""
    base = _setup(session_factory)
    entrada = _entrada(api_client, base, prestacion=base["endo"])
    turno = _turno(api_client, base)
    fake = FakeRedis()
    _usar_redis(fake)

    assert _cancelar(api_client, base, turno["id"]) == 200

    assert (
        _leer_entrada(session_factory, entrada["id"]).estado == "pendiente"
    )
    assert _mensajes_oferta(session_factory) == []
    assert fake.items == []


def test_entrada_dada_de_baja_no_recibe_oferta(
    api_client, session_factory
) -> None:
    """Edge: a soft-deleted entry is out of the FIFO."""
    base = _setup(session_factory)
    entrada = _entrada(api_client, base)
    assert (
        api_client.delete(
            f"/lista-espera/{entrada['id']}",
            headers=bearer(base["actores"]["recepcionista"]),
        ).status_code
        == 200
    )
    turno = _turno(api_client, base)
    _usar_redis(FakeRedis())

    assert _cancelar(api_client, base, turno["id"]) == 200

    assert _leer_entrada(session_factory, entrada["id"]).estado == "pendiente"
    assert _mensajes_oferta(session_factory) == []


def test_repetir_la_cancelacion_no_duplica_oferta_ni_auditoria(
    api_client, session_factory
) -> None:
    """Edge: the idempotent state change must not trigger a second offer."""
    base = _setup(session_factory)
    entrada = _entrada(api_client, base)
    turno = _turno(api_client, base)
    _usar_redis(FakeRedis())

    assert _cancelar(api_client, base, turno["id"]) == 200
    assert _cancelar(api_client, base, turno["id"]) == 200

    assert (
        _contar_auditoria(session_factory, "hueco_liberado", turno["id"]) == 1
    )
    assert len(_mensajes_oferta(session_factory)) == 1
    assert (
        _leer_entrada(session_factory, entrada["id"]).estado == "ofrecido"
    )


def test_dos_cancelaciones_concurrentes_dejan_una_sola_oferta(
    api_client, session_factory
) -> None:
    """Edge: overlapping freed ranges cannot retain twice (23P01/40P01)."""
    base = _setup(session_factory)
    primer_turno = _turno(api_client, base)
    sobreturno = _turno(
        api_client,
        base,
        es_sobreturno=True,
        color_sobreturno="#F97316",
    )
    _entrada(api_client, base)
    _entrada(api_client, base, paciente=base["paciente2"])
    _usar_redis(FakeRedis())

    def cancelar(turno_id: str) -> int:
        return _cancelar(api_client, base, turno_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        estados = list(
            pool.map(cancelar, [primer_turno["id"], sobreturno["id"]])
        )
    assert estados == [200, 200], estados

    async def ofrecidas():
        async with session_factory() as session:
            return list(
                await session.scalars(
                    select(EntradaListaEspera).where(
                        EntradaListaEspera.estado == "ofrecido"
                    )
                )
            )

    assert len(run(ofrecidas())) == 1
    assert len(_mensajes_oferta(session_factory)) == 1


# --- Mensaje, token y consulta pública --------------------------------------


def test_redis_caido_deja_el_mensaje_pendiente_y_la_cancelacion_responde_200(
    api_client, session_factory
) -> None:
    """Business error: Redis outage never breaks the cancellation (R-06)."""
    base = _setup(session_factory)
    entrada = _entrada(api_client, base)
    turno = _turno(api_client, base)
    _usar_redis(FakeRedis(ok=False))

    assert _cancelar(api_client, base, turno["id"]) == 200

    mensajes = _mensajes_oferta(session_factory)
    assert len(mensajes) == 1
    assert mensajes[0].estado_envio == "pendiente"
    assert mensajes[0].proximo_intento is not None
    assert (
        _leer_entrada(session_factory, entrada["id"]).estado == "ofrecido"
    )


def test_token_de_oferta_guarda_solo_hash_y_vence_con_la_oferta(
    api_client, session_factory
) -> None:
    """Expected: opaque single-use token, hashed, bounded by the offer TTL."""
    base = _setup(session_factory)
    entrada = _entrada(api_client, base)
    turno = _turno(api_client, base)
    _usar_redis(FakeRedis())
    assert _cancelar(api_client, base, turno["id"]) == 200

    mensaje = _mensajes_oferta(session_factory)[0]
    token = _token_de(mensaje)

    async def registro():
        async with session_factory() as session:
            return await session.scalar(
                select(TokenUnSoloUso).where(
                    TokenUnSoloUso.tipo == "oferta_hueco"
                )
            )

    emitido = run(registro())
    assert emitido is not None
    assert emitido.token_hash == hash_token(token)
    assert token != emitido.token_hash
    assert emitido.entidad_tipo == "entrada_lista_espera"
    assert emitido.entidad_id == entrada["id"]
    retenida = _leer_entrada(session_factory, entrada["id"])
    diferencia = emitido.expira_at - retenida.oferta_expira_en
    assert abs(diferencia.total_seconds()) < 120


def test_consulta_publica_de_la_oferta_no_consume_ni_expone_datos_sensibles(
    api_client, session_factory
) -> None:
    """Expected: 200 twice, same content, no phone/DNI/patient identity."""
    base = _setup(session_factory)
    _entrada(api_client, base)
    turno = _turno(api_client, base)
    _usar_redis(FakeRedis())
    assert _cancelar(api_client, base, turno["id"]) == 200
    mensaje = _mensajes_oferta(session_factory)[0]
    token = _token_de(mensaje)

    primera = api_client.get(f"/reservar/oferta/{token}")
    segunda = api_client.get(f"/reservar/oferta/{token}")
    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    assert primera.json() == segunda.json()

    body = primera.json()
    assert body["prestacion"]["codigo"] == "CONS"
    assert body["profesional"]["matricula"] == base["profesional"].matricula
    assert body["inicio"].startswith("2026-11-09T09:00:00-03:00")
    assert body["vence_en"]
    texto = primera.text.lower()
    assert "telefono" not in texto
    assert "dni" not in texto
    assert "turno demo" not in texto

    async def sin_consumir():
        async with session_factory() as session:
            return await session.scalar(
                select(TokenUnSoloUso.usado).where(
                    TokenUnSoloUso.token_hash == hash_token(token)
                )
            )

    assert run(sin_consumir()) is False


def test_consulta_de_oferta_vencida_devuelve_410(
    api_client, session_factory
) -> None:
    """Business error: an expired retention is not consultable."""
    base = _setup(session_factory)
    entrada = _entrada(api_client, base)
    turno = _turno(api_client, base)
    _usar_redis(FakeRedis())
    assert _cancelar(api_client, base, turno["id"]) == 200
    token = _token_de(_mensajes_oferta(session_factory)[0])

    async def expirar() -> None:
        async with session_factory() as session, session.begin():
            fila = await session.get(
                EntradaListaEspera, uuid.UUID(entrada["id"])
            )
            assert fila is not None
            fila.oferta_expira_en = datetime.now(timezone.utc) - timedelta(
                minutes=1
            )

    run(expirar())
    assert api_client.get(f"/reservar/oferta/{token}").status_code == 410


def test_consulta_de_oferta_ya_no_ofrecida_devuelve_410(
    api_client, session_factory
) -> None:
    """Business error: a token for a converted/expired entry is useless."""
    base = _setup(session_factory)
    entrada = _entrada(api_client, base)
    turno = _turno(api_client, base)
    _usar_redis(FakeRedis())
    assert _cancelar(api_client, base, turno["id"]) == 200
    token = _token_de(_mensajes_oferta(session_factory)[0])

    run(vencer_entrada(session_factory, uuid.UUID(entrada["id"])))
    assert api_client.get(f"/reservar/oferta/{token}").status_code == 410


def test_consulta_de_oferta_con_token_de_otro_proposito_devuelve_410(
    api_client, session_factory
) -> None:
    """Business error: a `gestion_turno` link is not an offer link (D8)."""
    base = _setup(session_factory)
    reserva = api_client.post(
        "/reservar/demo/turnos",
        json={
            "nombre": "Otro",
            "apellido": "Proposito",
            "dni": "43555555",
            "telefono": "11 4444-7777",
            "email": "otro.proposito@example.test",
            "profesional_id": str(base["profesional"].id),
            "prestacion_id": str(base["cons"]),
            "inicio": _hora(10).isoformat(),
        },
    )
    assert reserva.status_code == 201, reserva.text
    token = reserva.json()["gestion_url"].rsplit("/", 1)[-1]

    assert api_client.get(f"/reservar/oferta/{token}").status_code == 410


def test_consulta_de_oferta_con_token_reutilizado_devuelve_410(
    api_client, session_factory
) -> None:
    """Business error: a consumed token responds 410 (RN-NO-03)."""
    base = _setup(session_factory)
    _entrada(api_client, base)
    turno = _turno(api_client, base)
    _usar_redis(FakeRedis())
    assert _cancelar(api_client, base, turno["id"]) == 200
    token = _token_de(_mensajes_oferta(session_factory)[0])

    async def consumir() -> None:
        async with session_factory() as session, session.begin():
            await consume_single_use_token(
                session, token, expected_tipo="oferta_hueco"
            )

    run(consumir())
    assert api_client.get(f"/reservar/oferta/{token}").status_code == 410


def test_consulta_de_oferta_con_token_inexistente_devuelve_410(
    api_client, session_factory
) -> None:
    """Edge: an unknown token cannot reveal whether it ever existed."""
    _setup(session_factory)
    assert (
        api_client.get("/reservar/oferta/token-que-no-existe").status_code
        == 410
    )


@pytest.mark.parametrize("campo", ["telefono", "dni"])
def test_la_oferta_publica_no_declara_campos_sensibles(
    api_client, session_factory, campo: str
) -> None:
    """Edge: the response contract has no patient fields at all."""
    base = _setup(session_factory)
    _entrada(api_client, base)
    turno = _turno(api_client, base)
    _usar_redis(FakeRedis())
    assert _cancelar(api_client, base, turno["id"]) == 200
    token = _token_de(_mensajes_oferta(session_factory)[0])

    body = api_client.get(f"/reservar/oferta/{token}").json()
    assert campo not in json.dumps(body)
