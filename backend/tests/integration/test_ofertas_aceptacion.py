"""Offer acceptance: conversion with retained resources (C-10, tasks 7.1/7.2)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from sqlalchemy import func, select

from app.models import MensajeWhatsApp, Recordatorio, TokenUnSoloUso, Turno
from tests.integration.helpers import run
from tests.integration.ofertas_helpers import (
    FakeRedis,
    ahora,
    cancelar,
    crear_entrada,
    crear_turno,
    forzar_expiracion,
    hora,
    leer_entrada,
    mensajes_oferta,
    reservar_publico,
    setup_base,
    token_de,
)
from tests.integration.turnos_helpers import insertar_turno_db


def _aceptar(api_client, token: str):
    return api_client.post(f"/reservar/oferta/{token}/aceptar")


def _contar_turnos(session_factory, estado: str = "reservado") -> int:
    async def contar() -> int:
        async with session_factory() as session:
            return await session.scalar(
                select(func.count())
                .select_from(Turno)
                .where(Turno.estado == estado)
            )

    return run(contar())


def test_aceptar_crea_el_turno_con_los_recursos_retenidos(
    api_client, session_factory
) -> None:
    """Expected: the retained professional, chair and interval become a turn."""
    base = setup_base(session_factory)
    entrada = crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    token = token_de(mensajes_oferta(session_factory)[0])

    respuesta = _aceptar(api_client, token)
    assert respuesta.status_code == 200, respuesta.text
    body = respuesta.json()
    assert body["estado"] == "reservado"
    assert body["inicio"].startswith("2026-11-09T09:00:00-03:00")
    assert body["fin"].startswith("2026-11-09T09:30:00-03:00")
    assert body["sena"] == {
        "requiere": False,
        "monto": None,
        "estado": "no_requiere",
    }

    async def leer_turno() -> Turno:
        async with session_factory() as session:
            fila = await session.get(Turno, body["turno_id"])
            assert fila is not None
            return fila

    creado = run(leer_turno())
    assert creado.profesional_id == base["profesional"].id
    assert creado.sillon_id == base["sillon"].id
    assert creado.inicio == hora(9)
    assert creado.origen == "online"

    convertida = leer_entrada(session_factory, entrada["id"])
    assert convertida.estado == "convertido"
    assert str(convertida.turno_id) == body["turno_id"]
    assert convertida.oferta_inicio is None

    async def recordatorios() -> list[Recordatorio]:
        async with session_factory() as session:
            return list(
                await session.scalars(
                    select(Recordatorio).where(
                        Recordatorio.turno_id == creado.id
                    )
                )
            )

    ventanas = {fila.ventana for fila in run(recordatorios())}
    assert "24h" in ventanas
    # The 48 h reminder is only programmed when the turn is far enough away.
    if hora(9) - ahora() > timedelta(hours=48):
        assert "48h" in ventanas

    async def token_usado() -> bool:
        async with session_factory() as session:
            usado = await session.scalar(
                select(TokenUnSoloUso.usado)
                .where(TokenUnSoloUso.tipo == "oferta_hueco")
                .order_by(TokenUnSoloUso.created_at.desc())
                .limit(1)
            )
            return bool(usado)

    assert run(token_usado()) is True


def test_aceptar_dos_veces_devuelve_410(
    api_client, session_factory
) -> None:
    """Business error: the link is single use."""
    base = setup_base(session_factory)
    crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    token = token_de(mensajes_oferta(session_factory)[0])

    assert _aceptar(api_client, token).status_code == 200
    assert _aceptar(api_client, token).status_code == 410
    assert _contar_turnos(session_factory) == 1


def test_aceptar_retencion_vencida_con_el_horario_tomado_devuelve_409(
    api_client, session_factory
) -> None:
    """Business error: 409, the entry expires and no second turn is created."""
    base = setup_base(session_factory)
    entrada = crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    token = token_de(mensajes_oferta(session_factory)[0])

    forzar_expiracion(session_factory, entrada["id"], ahora())
    run(
        insertar_turno_db(
            session_factory,
            consultorio_id=base["consultorio_id"],
            paciente_id=base["paciente2"].id,
            profesional_id=base["profesional"].id,
            sillon_id=base["sillon"].id,
            inicio=hora(9),
            fin=hora(9, 30),
        )
    )

    respuesta = _aceptar(api_client, token)
    assert respuesta.status_code == 409, respuesta.text
    assert leer_entrada(session_factory, entrada["id"]).estado == "vencido"
    assert _contar_turnos(session_factory) == 1


def test_aceptar_una_oferta_vencida_y_libre_devuelve_410(
    api_client, session_factory
) -> None:
    """Business error: past the TTL the link is gone even if the slot is free."""
    base = setup_base(session_factory)
    entrada = crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    token = token_de(mensajes_oferta(session_factory)[0])

    forzar_expiracion(session_factory, entrada["id"], ahora())
    assert _aceptar(api_client, token).status_code == 410
    assert _contar_turnos(session_factory) == 0


def test_aceptar_con_token_invalido_o_de_otro_proposito(
    api_client, session_factory
) -> None:
    """Business error: unknown tokens and management links answer 410 (D8)."""
    base = setup_base(session_factory)
    assert _aceptar(api_client, "token-que-no-existe").status_code == 410

    reserva = reservar_publico(api_client, base, inicio=hora(10).isoformat())
    assert reserva.status_code == 201, reserva.text
    gestion = reserva.json()["gestion_url"].rsplit("/", 1)[-1]
    assert _aceptar(api_client, gestion).status_code == 410


def test_dos_aceptaciones_concurrentes_crean_un_solo_turno(
    api_client, session_factory
) -> None:
    """Edge: exactly one acceptance wins the offer."""
    base = setup_base(session_factory)
    crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    token = token_de(mensajes_oferta(session_factory)[0])

    def aceptar(_: int) -> int:
        return _aceptar(api_client, token).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        estados = list(pool.map(aceptar, range(2)))

    assert sorted(estados) == [200, 410], estados
    assert _contar_turnos(session_factory) == 1


def test_reserva_publica_simultanea_al_vencer_deja_un_solo_turno(
    api_client, session_factory
) -> None:
    """Edge: the public flow and the link cannot both book the same slot."""
    base = setup_base(session_factory)
    entrada = crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    token = token_de(mensajes_oferta(session_factory)[0])
    forzar_expiracion(session_factory, entrada["id"], ahora())

    def reservar(_: int) -> int:
        return reservar_publico(api_client, base).status_code

    def aceptar(_: int) -> int:
        return _aceptar(api_client, token).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futuros = [
            pool.submit(reservar, 0),
            pool.submit(aceptar, 1),
        ]
        estados = sorted(futuro.result() for futuro in futuros)

    assert estados.count(201) == 1, estados
    otro = next(estado for estado in estados if estado != 201)
    assert otro in {409, 410}, estados
    assert _contar_turnos(session_factory) == 1


def test_aceptar_marca_el_mensaje_de_oferta_como_consumido(
    api_client, session_factory
) -> None:
    """Edge: the offer message and token reflect the conversion."""
    base = setup_base(session_factory)
    entrada = crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    mensaje = mensajes_oferta(session_factory)[0]

    assert _aceptar(api_client, token_de(mensaje)).status_code == 200

    async def leer_mensaje() -> MensajeWhatsApp:
        async with session_factory() as session:
            fila = await session.get(MensajeWhatsApp, mensaje.id)
            assert fila is not None
            return fila

    assert str(run(leer_mensaje()).lista_espera_id) == entrada["id"]


def test_la_conversion_no_deja_retencion_activa(
    api_client, session_factory
) -> None:
    """Edge: after converting, the turn is the only occupant of the interval."""
    base = setup_base(session_factory)
    crear_entrada(api_client, base)
    turno = crear_turno(api_client, base)
    assert cancelar(api_client, base, turno["id"]) == 200
    token = token_de(mensajes_oferta(session_factory)[0])

    assert _aceptar(api_client, token).status_code == 200

    async def ofrecidas() -> int:
        from app.models import EntradaListaEspera

        async with session_factory() as session:
            return await session.scalar(
                select(func.count())
                .select_from(EntradaListaEspera)
                .where(EntradaListaEspera.estado == "ofrecido")
            )

    assert run(ofrecidas()) == 0
    assert _aceptar(api_client, token).status_code == 410
