"""Offer expiry, rotation and link rejection (C-10, tasks 6.1/6.2)."""

import uuid
from datetime import timedelta

from sqlalchemy import select

from app.application.lista_espera import procesar_ofertas_vencidas
from app.infrastructure.uow import UnitOfWork
from app.models import Turno
from tests.integration.helpers import run
from tests.integration.lista_espera_helpers import convertir_entrada
from tests.integration.ofertas_helpers import (
    FakeRedis,
    ahora,
    cancelar,
    contar_auditoria,
    crear_entrada,
    crear_turno,
    forzar_expiracion,
    hora,
    leer_entrada,
    mensajes_oferta,
    setup_base,
    token_de,
)
from tests.integration.turnos_helpers import insertar_turno_db


def _sweep(session_factory, fake: FakeRedis, cuando, ttl: int = 30) -> int:
    async def procesar() -> int:
        async with UnitOfWork(session_factory) as uow:
            return await procesar_ofertas_vencidas(
                uow,
                fake,
                now=cuando,
                base_url="http://127.0.0.1:8080",
                ttl_minutos=ttl,
            )

    return run(procesar())


# --- Vencimiento y rotación -------------------------------------------------


def test_vencimiento_en_el_borde_exacto_libera_y_rota(
    api_client, session_factory
) -> None:
    """Expected: `oferta_expira_en == now` expires and rotates to the next."""
    base = setup_base(session_factory)
    primera = crear_entrada(api_client, base)
    segunda = crear_entrada(api_client, base, paciente=base["paciente2"])
    turno = crear_turno(api_client, base)
    fake = FakeRedis()
    assert cancelar(api_client, base, turno["id"]) == 200

    borde = ahora()
    forzar_expiracion(session_factory, primera["id"], borde)
    procesadas = _sweep(session_factory, fake, borde)

    assert procesadas == 1
    vencida = leer_entrada(session_factory, primera["id"])
    assert vencida.estado == "vencido"
    assert vencida.oferta_inicio is None
    assert vencida.oferta_expira_en is None

    siguiente = leer_entrada(session_factory, segunda["id"])
    assert siguiente.estado == "ofrecido"
    assert siguiente.oferta_profesional_id == base["profesional"].id
    assert siguiente.oferta_sillon_id == base["sillon"].id
    assert siguiente.oferta_inicio == hora(9)
    assert siguiente.oferta_fin == hora(9, 30)
    assert siguiente.oferta_expira_en > borde

    mensajes = mensajes_oferta(session_factory)
    assert len(mensajes) == 2
    assert mensajes[-1].lista_espera_id == uuid.UUID(segunda["id"])
    assert fake.items[-1] == ("whatsapp:send", str(mensajes[-1].id))
    assert (
        contar_auditoria(session_factory, "oferta_hueco_vencida", primera["id"])
        == 1
    )


def test_vencida_con_el_hueco_ya_tomado_no_rota(
    api_client, session_factory
) -> None:
    """Business error: an occupied range is not offered again (D5)."""
    base = setup_base(session_factory)
    primera = crear_entrada(api_client, base)
    segunda = crear_entrada(api_client, base, paciente=base["paciente2"])
    turno = crear_turno(api_client, base)
    fake = FakeRedis()
    assert cancelar(api_client, base, turno["id"]) == 200

    borde = ahora()
    forzar_expiracion(session_factory, primera["id"], borde)
    run(
        insertar_turno_db(
            session_factory,
            consultorio_id=base["consultorio_id"],
            paciente_id=base["paciente"].id,
            profesional_id=base["profesional"].id,
            sillon_id=base["sillon"].id,
            inicio=hora(9),
            fin=hora(9, 30),
        )
    )

    assert _sweep(session_factory, fake, borde) == 1

    assert leer_entrada(session_factory, primera["id"]).estado == "vencido"
    assert leer_entrada(session_factory, segunda["id"]).estado == "pendiente"
    assert len(mensajes_oferta(session_factory)) == 1
    assert fake.items == []


def test_la_ultima_oferta_vencida_devuelve_el_hueco_a_disponibilidad(
    api_client, session_factory
) -> None:
    """Edge: with nobody left the slot reappears in the public agenda."""
    base = setup_base(session_factory)
    entrada = crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    fake = FakeRedis()
    assert cancelar(api_client, base, turno["id"]) == 200

    borde = ahora()
    forzar_expiracion(session_factory, entrada["id"], borde)
    assert _sweep(session_factory, fake, borde) == 1

    disponible = api_client.get(
        "/reservar/demo/disponibilidad",
        params={
            "fecha": "2026-11-09",
            "profesional_id": str(base["profesional"].id),
            "prestacion_id": str(base["cons"]),
        },
    )
    assert disponible.status_code == 200, disponible.text
    assert "2026-11-09T09:00:00-03:00" in [
        slot["inicio"] for slot in disponible.json()
    ]


def test_vencer_fuera_de_ventana_no_procesa(api_client, session_factory) -> None:
    """Edge: a still-live offer is not swept."""
    base = setup_base(session_factory)
    entrada = crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    fake = FakeRedis()
    assert cancelar(api_client, base, turno["id"]) == 200

    assert _sweep(session_factory, fake, ahora()) == 0
    assert leer_entrada(session_factory, entrada["id"]).estado == "ofrecido"


# --- Rechazo por enlace -----------------------------------------------------


def test_rechazo_libera_y_rota_al_siguiente_con_el_mismo_sillon(
    api_client, session_factory
) -> None:
    """Expected: rejection releases and offers the same chair to the next."""
    base = setup_base(session_factory)
    primera = crear_entrada(api_client, base)
    segunda = crear_entrada(api_client, base, paciente=base["paciente2"])
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    token = token_de(mensajes_oferta(session_factory)[0])

    respuesta = api_client.post(f"/reservar/oferta/{token}/rechazar")
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json() == {"estado": "vencido"}

    rechazada = leer_entrada(session_factory, primera["id"])
    assert rechazada.estado == "vencido"
    assert rechazada.oferta_inicio is None

    siguiente = leer_entrada(session_factory, segunda["id"])
    assert siguiente.estado == "ofrecido"
    assert siguiente.oferta_sillon_id == base["sillon"].id
    assert siguiente.oferta_profesional_id == base["profesional"].id
    assert siguiente.oferta_inicio == hora(9)
    assert len(mensajes_oferta(session_factory)) == 2
    assert (
        contar_auditoria(
            session_factory, "oferta_hueco_rechazada", primera["id"]
        )
        == 1
    )


def test_rechazo_sin_siguiente_devuelve_el_hueco_a_disponibilidad(
    api_client, session_factory
) -> None:
    """Edge: rejecting the last entry releases the slot publicly."""
    base = setup_base(session_factory)
    entrada = crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    token = token_de(mensajes_oferta(session_factory)[0])

    assert api_client.post(f"/reservar/oferta/{token}/rechazar").status_code == 200
    assert leer_entrada(session_factory, entrada["id"]).estado == "vencido"

    disponible = api_client.get(
        "/reservar/demo/disponibilidad",
        params={
            "fecha": "2026-11-09",
            "profesional_id": str(base["profesional"].id),
            "prestacion_id": str(base["cons"]),
        },
    )
    assert "2026-11-09T09:00:00-03:00" in [
        slot["inicio"] for slot in disponible.json()
    ]


def test_rechazo_repetido_devuelve_410(
    api_client, session_factory
) -> None:
    """Business error: the token is single use (RN-NO-03)."""
    base = setup_base(session_factory)
    crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    token = token_de(mensajes_oferta(session_factory)[0])

    assert api_client.post(f"/reservar/oferta/{token}/rechazar").status_code == 200
    assert api_client.post(f"/reservar/oferta/{token}/rechazar").status_code == 410


def test_rechazo_de_una_oferta_convertida_devuelve_410(
    api_client, session_factory
) -> None:
    """Business error: a converted entry cannot be rejected."""
    base = setup_base(session_factory)
    entrada = crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    token = token_de(mensajes_oferta(session_factory)[0])

    convertido = run(
        insertar_turno_db(
            session_factory,
            consultorio_id=base["consultorio_id"],
            paciente_id=base["paciente"].id,
            profesional_id=base["profesional"].id,
            sillon_id=base["sillon"].id,
            inicio=hora(9),
            fin=hora(9, 30),
        )
    )
    run(convertir_entrada(session_factory, uuid.UUID(entrada["id"]), convertido))

    respuesta = api_client.post(f"/reservar/oferta/{token}/rechazar")
    assert respuesta.status_code == 410, respuesta.text

    async def contar_reservados() -> int:
        async with session_factory() as session:
            turnos = list(
                await session.scalars(
                    select(Turno).where(Turno.estado == "reservado")
                )
            )
            return len(turnos)

    assert run(contar_reservados()) == 1


def test_rechazo_con_token_de_otro_proposito_devuelve_410(
    api_client, session_factory
) -> None:
    """Business error: a management token is not an offer token (D8)."""
    base = setup_base(session_factory)
    crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    reserva = api_client.post(
        "/reservar/demo/turnos",
        json={
            "nombre": "Otro",
            "apellido": "Token",
            "dni": "43666888",
            "telefono": "11 5555-7777",
            "email": "otro.token@example.test",
            "profesional_id": str(base["profesional"].id),
            "prestacion_id": str(base["cons"]),
            "inicio": hora(10).isoformat(),
        },
    )
    assert reserva.status_code == 201, reserva.text
    token = reserva.json()["gestion_url"].rsplit("/", 1)[-1]
    assert cancelar(api_client, base, turno["id"]) == 200

    assert (
        api_client.post(f"/reservar/oferta/{token}/rechazar").status_code == 410
    )


def test_vencida_con_hueco_libre_rota_con_el_ttl_configurado(
    api_client, session_factory
) -> None:
    """Edge: the rotated offer gets a fresh TTL from the sweep clock."""
    base = setup_base(session_factory)
    primera = crear_entrada(api_client, base)
    segunda = crear_entrada(api_client, base, paciente=base["paciente2"])
    turno = crear_turno(api_client, base)
    fake = FakeRedis()
    assert cancelar(api_client, base, turno["id"]) == 200

    borde = ahora()
    forzar_expiracion(session_factory, primera["id"], borde)
    _sweep(session_factory, fake, borde, ttl=15)

    siguiente = leer_entrada(session_factory, segunda["id"])
    assert siguiente.estado == "ofrecido"
    assert siguiente.oferta_expira_en is not None
    assert abs(
        (siguiente.oferta_expira_en - (borde + timedelta(minutes=15)))
        .total_seconds()
    ) < 1
