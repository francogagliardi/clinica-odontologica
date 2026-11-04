"""Appointments: duration, anti-overlap, sobreturnos, blocks, states, RBAC (C-06)."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.domain.agenda import ARGENTINA_OFFSET
from tests.integration.helpers import run, sqlstate
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.recursos_helpers import (
    bearer,
    create_profesional,
    create_sillon,
)
from tests.integration.turnos_helpers import (
    FECHA_LUNES,
    INICIO,
    prestacion_id,
    setup_turnos,
    turno_payload,
)


def _hora(hora: int, minuto: int = 0, dia: int = 9) -> datetime:
    return datetime(2026, 11, dia, hora, minuto, tzinfo=ARGENTINA_OFFSET)


def _crear(api_client, actor, payload):
    return api_client.post("/turnos", json=payload, headers=bearer(actor))


def _semana(actor):
    return {
        "desde": "2026-11-09",
        "hasta": "2026-11-15",
    }


def _listar(api_client, actor, **params):
    return api_client.get(
        "/turnos", params={**_semana(actor), **params}, headers=bearer(actor)
    )


def _setup(session_factory) -> dict[str, object]:
    return run(setup_turnos(session_factory))


def _payload(base: dict[str, object], **overrides) -> dict[str, object]:
    return turno_payload(
        paciente_id=base["paciente"].id,
        profesional_id=base["profesional"].id,
        sillon_id=base["sillon"].id,
        **overrides,
    )


def _crear_ok(api_client, base, **overrides) -> dict[str, object]:
    respuesta = _crear(
        api_client, base["actores"]["recepcionista"], _payload(base, **overrides)
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _cambiar(api_client, actor, turno_id: str, estado: str):
    return api_client.patch(
        f"/turnos/{turno_id}/estado",
        json={"estado": estado},
        headers=bearer(actor),
    )


def _reprogramar(api_client, actor, turno_id: str, body: dict[str, object]):
    return api_client.patch(
        f"/turnos/{turno_id}/reprogramar",
        json=body,
        headers=bearer(actor),
    )


def _sql_insertar_turno(
    session_factory,
    consultorio_id,
    paciente_id,
    profesional_id,
    sillon_id,
    inicio: datetime,
    fin: datetime,
) -> None:
    async def insertar() -> None:
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "INSERT INTO turnos "
                    "(id, consultorio_id, paciente_id, profesional_id, "
                    "sillon_id, inicio, fin) "
                    "VALUES (:id, :consultorio_id, :paciente_id, "
                    ":profesional_id, :sillon_id, :inicio, :fin)"
                ),
                {
                    "id": uuid.uuid4(),
                    "consultorio_id": consultorio_id,
                    "paciente_id": paciente_id,
                    "profesional_id": profesional_id,
                    "sillon_id": sillon_id,
                    "inicio": inicio,
                    "fin": fin,
                },
            )

    run(insertar())


# --- 4. Alta y duración -----------------------------------------------------


def test_alta_con_prestacion_calcula_el_fin(api_client, session_factory) -> None:
    """Expected: ENDO (90 min) ends 10:30 and starts as reservado."""
    base = _setup(session_factory)
    endo = run(prestacion_id(session_factory, "ENDO"))

    turno = _crear_ok(
        api_client,
        base,
        prestacion_id=endo,
        inicio=_hora(9).isoformat(),
    )
    assert turno["estado"] == "reservado"
    assert turno["origen"] == "recepcion"
    assert datetime.fromisoformat(turno["fin"]) == _hora(10, 30)
    assert turno["es_sobreturno"] is False


def test_alta_sin_prestacion_usa_duracion_base(api_client, session_factory) -> None:
    """Expected: no service means the professional's 60-minute base."""
    base = _setup(session_factory)
    turno = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    assert datetime.fromisoformat(turno["fin"]) == _hora(10)


@pytest.mark.parametrize(
    "recurso",
    ["paciente_id", "profesional_id", "sillon_id", "prestacion_id"],
)
def test_recurso_inexistente_devuelve_404(
    api_client, session_factory, recurso: str
) -> None:
    """Business error: every resource must exist and be active."""
    base = _setup(session_factory)
    payload = _payload(
        base, prestacion_id=run(prestacion_id(session_factory, "CONS"))
    )
    payload[recurso] = str(uuid.uuid4())
    respuesta = _crear(
        api_client, base["actores"]["recepcionista"], payload
    )
    assert respuesta.status_code == 404, respuesta.text


@pytest.mark.parametrize(
    "inicio",
    [
        _hora(9, dia=14),  # Saturday
        _hora(11, 30),  # 60 min ends at 12:30, after hora_hasta
        _hora(8, 30),  # starts before hora_desde
    ],
)
def test_turno_fuera_de_agenda_devuelve_422(
    api_client, session_factory, inicio: datetime
) -> None:
    """Business rule: the turn must fit the professional's agenda."""
    base = _setup(session_factory)
    respuesta = _crear(
        api_client,
        base["actores"]["recepcionista"],
        _payload(base, inicio=inicio.isoformat()),
    )
    assert respuesta.status_code == 422, respuesta.text


def test_fin_no_posterior_es_rechazado_por_la_base(session_factory) -> None:
    """Edge: the CHECK rejects a direct insert with fin == inicio."""
    base = _setup(session_factory)
    with pytest.raises(IntegrityError) as error:
        _sql_insertar_turno(
            session_factory,
            base["consultorio_id"],
            base["paciente"].id,
            base["profesional"].id,
            base["sillon"].id,
            _hora(9),
            _hora(9),
        )
    assert sqlstate(error.value) == "23514"


@pytest.mark.parametrize(
    "extra",
    [
        {"fin": _hora(10).isoformat()},
        {"estado": "confirmado"},
        {"origen": "telefono"},
    ],
)
def test_payload_invalido_devuelve_422(
    api_client, session_factory, extra: dict[str, object]
) -> None:
    """Edge: clients cannot set server-derived fields."""
    base = _setup(session_factory)
    payload = _payload(base, inicio=_hora(9).isoformat(), **extra)
    assert (
        _crear(api_client, base["actores"]["recepcionista"], payload).status_code
        == 422
    )


# --- 5. Anti-solapamiento ---------------------------------------------------


def test_mismo_profesional_solapado_devuelve_409(
    api_client, session_factory
) -> None:
    """Business error: one professional cannot be in two places at once."""
    base = _setup(session_factory)
    _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    otro_sillon = run(
        create_sillon(
            session_factory, base["consultorio_id"], "Sillon B"
        )
    )
    respuesta = _crear(
        api_client,
        base["actores"]["recepcionista"],
        turno_payload(
            paciente_id=base["paciente"].id,
            profesional_id=base["profesional"].id,
            sillon_id=otro_sillon.id,
            inicio=_hora(9, 30).isoformat(),
        ),
    )
    assert respuesta.status_code == 409, respuesta.text


def test_mismo_sillon_con_otro_profesional_devuelve_409(
    api_client, session_factory
) -> None:
    """Business error: the chair is an exclusion resource too."""
    base = _setup(session_factory)
    _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    otro_profesional = run(
        create_profesional(
            session_factory, base["consultorio_id"], "MP-TURNOS-2"
        )
    )
    respuesta = _crear(
        api_client,
        base["actores"]["recepcionista"],
        turno_payload(
            paciente_id=base["paciente"].id,
            profesional_id=otro_profesional.id,
            sillon_id=base["sillon"].id,
            inicio=_hora(9, 30).isoformat(),
        ),
    )
    assert respuesta.status_code == 409, respuesta.text


def test_turnos_consecutivos_se_permiten(api_client, session_factory) -> None:
    """Edge: half-open intervals allow back-to-back appointments."""
    base = _setup(session_factory)
    _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    _crear_ok(api_client, base, inicio=_hora(10).isoformat())


def test_recursos_distintos_en_el_mismo_horario(api_client, session_factory) -> None:
    """Edge: two different professionals/chairs can share a time."""
    base = _setup(session_factory)
    otro_profesional = run(
        create_profesional(
            session_factory, base["consultorio_id"], "MP-TURNOS-3"
        )
    )
    otro_sillon = run(
        create_sillon(session_factory, base["consultorio_id"], "Sillon C")
    )
    _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    respuesta = _crear(
        api_client,
        base["actores"]["recepcionista"],
        turno_payload(
            paciente_id=base["paciente"].id,
            profesional_id=otro_profesional.id,
            sillon_id=otro_sillon.id,
            inicio=_hora(9).isoformat(),
        ),
    )
    assert respuesta.status_code == 201, respuesta.text


def test_turno_cancelado_libera_el_horario(api_client, session_factory) -> None:
    """Edge: cancelled/absent turns do not block new bookings."""
    base = _setup(session_factory)
    turno = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    assert (
        _cambiar(
            api_client, base["actores"]["recepcionista"], turno["id"], "cancelado"
        ).status_code
        == 200
    )
    _crear_ok(api_client, base, inicio=_hora(9).isoformat())


def test_dos_altas_concurrentes_al_mismo_slot(api_client, session_factory) -> None:
    """Edge: the database guarantees one winner under real concurrency."""
    base = _setup(session_factory)
    headers = bearer(base["actores"]["recepcionista"])
    payload = _payload(base, inicio=_hora(9).isoformat())

    def reservar() -> int:
        return api_client.post("/turnos", json=payload, headers=headers).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        estados = list(pool.map(lambda _: reservar(), range(2)))

    assert sorted(estados) == [201, 409], estados
    listado = _listar(api_client, base["actores"]["recepcionista"])
    assert len(listado.json()) == 1


def test_solapamiento_por_sql_directo_es_rechazado(session_factory) -> None:
    """Edge: the exclusion constraint protects even outside the API."""
    base = _setup(session_factory)
    _sql_insertar_turno(
        session_factory,
        base["consultorio_id"],
        base["paciente"].id,
        base["profesional"].id,
        base["sillon"].id,
        _hora(9),
        _hora(10),
    )
    otro_sillon = run(
        create_sillon(session_factory, base["consultorio_id"], "Sillon SQL")
    )
    with pytest.raises(IntegrityError) as error:
        _sql_insertar_turno(
            session_factory,
            base["consultorio_id"],
            base["paciente"].id,
            base["profesional"].id,
            otro_sillon.id,
            _hora(9),
            _hora(10),
        )
    assert sqlstate(error.value) == "23P01"


# --- 6. Sobreturnos ---------------------------------------------------------


def test_sobreturno_marcado_se_permite(api_client, session_factory) -> None:
    """Expected: the only allowed overlap, with visible mark and colour."""
    base = _setup(session_factory)
    _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    sobreturno = _crear_ok(
        api_client,
        base,
        inicio=_hora(9, 30).isoformat(),
        es_sobreturno=True,
        color_sobreturno="#F97316",
    )
    assert sobreturno["es_sobreturno"] is True
    assert sobreturno["color_sobreturno"] == "#F97316"


def test_sobreturno_sin_color_devuelve_422(api_client, session_factory) -> None:
    """Business error: the mark is not enough; the colour is required."""
    base = _setup(session_factory)
    respuesta = _crear(
        api_client,
        base["actores"]["recepcionista"],
        _payload(
            base,
            inicio=_hora(9).isoformat(),
            es_sobreturno=True,
        ),
    )
    assert respuesta.status_code == 422


def test_color_sin_marca_devuelve_422(api_client, session_factory) -> None:
    """Edge: colour only applies to sobreturnos."""
    base = _setup(session_factory)
    respuesta = _crear(
        api_client,
        base["actores"]["recepcionista"],
        _payload(
            base,
            inicio=_hora(9).isoformat(),
            color_sobreturno="#F97316",
        ),
    )
    assert respuesta.status_code == 422


def test_turno_normal_contra_sobreturno_devuelve_409(
    api_client, session_factory
) -> None:
    """Business error: only the marked sobreturno may overlap."""
    base = _setup(session_factory)
    _crear_ok(
        api_client,
        base,
        inicio=_hora(9).isoformat(),
        es_sobreturno=True,
        color_sobreturno="#F97316",
    )
    respuesta = _crear(
        api_client,
        base["actores"]["recepcionista"],
        _payload(base, inicio=_hora(9, 30).isoformat()),
    )
    assert respuesta.status_code == 409, respuesta.text


# --- 7. Bloqueos ------------------------------------------------------------


def _bloquear(api_client, actor, **body):
    return api_client.post("/bloqueos", json=body, headers=bearer(actor))


def test_bloqueo_del_profesional_impide_reservar(
    api_client, session_factory
) -> None:
    """Business error: a professional block removes the slot."""
    base = _setup(session_factory)
    assert (
        _bloquear(
            api_client,
            base["actores"]["recepcionista"],
            profesional_id=str(base["profesional"].id),
            desde=_hora(9, 30).isoformat(),
            hasta=_hora(10, 30).isoformat(),
            motivo="Licencia",
        ).status_code
        == 201
    )
    respuesta = _crear(
        api_client,
        base["actores"]["recepcionista"],
        _payload(base, inicio=_hora(9, 30).isoformat()),
    )
    assert respuesta.status_code == 409, respuesta.text


def test_bloqueo_del_sillon_impide_reservar(api_client, session_factory) -> None:
    """Business error: a chair block removes the slot even if the pro is free."""
    base = _setup(session_factory)
    assert (
        _bloquear(
            api_client,
            base["actores"]["recepcionista"],
            sillon_id=str(base["sillon"].id),
            desde=_hora(9, 30).isoformat(),
            hasta=_hora(10, 30).isoformat(),
            motivo="Mantenimiento",
        ).status_code
        == 201
    )
    respuesta = _crear(
        api_client,
        base["actores"]["recepcionista"],
        _payload(base, inicio=_hora(9, 30).isoformat()),
    )
    assert respuesta.status_code == 409, respuesta.text


def test_bloqueo_adyacente_no_afecta(api_client, session_factory) -> None:
    """Edge: a block ending exactly at the start does not collide."""
    base = _setup(session_factory)
    _bloquear(
        api_client,
        base["actores"]["recepcionista"],
        profesional_id=str(base["profesional"].id),
        desde=_hora(8).isoformat(),
        hasta=_hora(9).isoformat(),
        motivo="Reunión",
    )
    _crear_ok(api_client, base, inicio=_hora(9).isoformat())


def test_bloqueo_de_otro_recurso_no_afecta(api_client, session_factory) -> None:
    """Edge: blocks only affect their own professional/chair."""
    base = _setup(session_factory)
    otro_profesional = run(
        create_profesional(
            session_factory, base["consultorio_id"], "MP-TURNOS-4"
        )
    )
    _bloquear(
        api_client,
        base["actores"]["recepcionista"],
        profesional_id=str(otro_profesional.id),
        desde=_hora(9).isoformat(),
        hasta=_hora(10).isoformat(),
        motivo="Otro",
    )
    _crear_ok(api_client, base, inicio=_hora(9).isoformat())


# --- 8. Estados y reprogramación -------------------------------------------


def test_transiciones_validas_del_flujo(api_client, session_factory) -> None:
    """Expected: reservado → confirmado → en_sala → atendido."""
    base = _setup(session_factory)
    turno = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    actor = base["actores"]["recepcionista"]
    for estado in ("confirmado", "en_sala", "atendido"):
        respuesta = _cambiar(api_client, actor, turno["id"], estado)
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["estado"] == estado


@pytest.mark.parametrize(
    ("origen", "destino"),
    [
        ("reservado", "atendido"),
        ("reservado", "en_sala"),
        ("cancelado", "confirmado"),
    ],
)
def test_transiciones_invalidas_devuelven_422(
    api_client, session_factory, origen: str, destino: str
) -> None:
    """Business error: the state machine rejects skips and revivals."""
    base = _setup(session_factory)
    turno = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    actor = base["actores"]["recepcionista"]
    if origen == "cancelado":
        assert _cambiar(api_client, actor, turno["id"], "cancelado").status_code == 200
    respuesta = _cambiar(api_client, actor, turno["id"], destino)
    assert respuesta.status_code == 422, respuesta.text
    assert (
        api_client.get(f"/turnos/{turno['id']}", headers=bearer(actor))
        .json()["estado"]
        == origen
    )


@pytest.mark.parametrize("origen", ["reservado", "confirmado"])
def test_cancelacion_desde_estados_validos(
    api_client, session_factory, origen: str
) -> None:
    """Expected: cancelling frees the slot again."""
    base = _setup(session_factory)
    turno = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    actor = base["actores"]["recepcionista"]
    if origen == "confirmado":
        _cambiar(api_client, actor, turno["id"], "confirmado")
    respuesta = _cambiar(api_client, actor, turno["id"], "cancelado")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "cancelado"


def test_repetir_estado_es_idempotente(api_client, session_factory) -> None:
    """Edge: retries do not fail nor change the row."""
    base = _setup(session_factory)
    turno = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    actor = base["actores"]["recepcionista"]
    _cambiar(api_client, actor, turno["id"], "confirmado")
    repetido = _cambiar(api_client, actor, turno["id"], "confirmado")
    assert repetido.status_code == 200
    assert repetido.json()["estado"] == "confirmado"


def test_cambio_de_estado_de_turno_inexistente(api_client, session_factory) -> None:
    """Business error: unknown appointments are 404."""
    base = _setup(session_factory)
    respuesta = _cambiar(
        api_client,
        base["actores"]["recepcionista"],
        str(uuid.uuid4()),
        "confirmado",
    )
    assert respuesta.status_code == 404


def test_reprogramacion_a_horario_libre(api_client, session_factory) -> None:
    """Expected: new start recalculates the end and keeps the state."""
    base = _setup(session_factory)
    turno = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    actor = base["actores"]["recepcionista"]
    _cambiar(api_client, actor, turno["id"], "confirmado")

    respuesta = _reprogramar(
        api_client, actor, turno["id"], {"inicio": _hora(11).isoformat()}
    )
    assert respuesta.status_code == 200, respuesta.text
    assert datetime.fromisoformat(respuesta.json()["inicio"]) == _hora(11)
    assert datetime.fromisoformat(respuesta.json()["fin"]) == _hora(12)
    assert respuesta.json()["estado"] == "confirmado"


def test_reprogramacion_a_horario_ocupado_deja_intacto(
    api_client, session_factory
) -> None:
    """Business error: a failed move does not modify the original row."""
    base = _setup(session_factory)
    turno = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    _crear_ok(api_client, base, inicio=_hora(10).isoformat())
    actor = base["actores"]["recepcionista"]

    respuesta = _reprogramar(
        api_client, actor, turno["id"], {"inicio": _hora(10).isoformat()}
    )
    assert respuesta.status_code == 409, respuesta.text
    ficha = api_client.get(f"/turnos/{turno['id']}", headers=bearer(actor))
    assert datetime.fromisoformat(ficha.json()["inicio"]) == _hora(9)


def test_reprogramacion_fuera_de_agenda_o_sobre_bloqueo(
    api_client, session_factory
) -> None:
    """Error: agenda window is 422 and a block is 409."""
    base = _setup(session_factory)
    turno = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    actor = base["actores"]["recepcionista"]

    fuera = _reprogramar(
        api_client, actor, turno["id"], {"inicio": _hora(11, 30).isoformat()}
    )
    assert fuera.status_code == 422, fuera.text

    _bloquear(
        api_client,
        actor,
        profesional_id=str(base["profesional"].id),
        desde=_hora(11).isoformat(),
        hasta=_hora(12).isoformat(),
        motivo="Bloqueo",
    )
    bloqueado = _reprogramar(
        api_client, actor, turno["id"], {"inicio": _hora(11).isoformat()}
    )
    assert bloqueado.status_code == 409, bloqueado.text


def test_reprogramar_turno_cerrado_devuelve_422(
    api_client, session_factory
) -> None:
    """Business error: cancelled/attended turns are historical."""
    base = _setup(session_factory)
    turno = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    actor = base["actores"]["recepcionista"]
    _cambiar(api_client, actor, turno["id"], "cancelado")
    respuesta = _reprogramar(
        api_client, actor, turno["id"], {"inicio": _hora(10).isoformat()}
    )
    assert respuesta.status_code == 422


def test_reprogramaciones_concurrentes_al_mismo_slot(
    api_client, session_factory
) -> None:
    """Edge: only one move wins when two target the same free slot."""
    base = _setup(session_factory)
    primero = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    segundo = _crear_ok(api_client, base, inicio=_hora(10).isoformat())
    actor = base["actores"]["recepcionista"]
    headers = bearer(actor)

    def mover(turno_id: str) -> int:
        return api_client.patch(
            f"/turnos/{turno_id}/reprogramar",
            json={"inicio": _hora(11).isoformat()},
            headers=headers,
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        estados = list(
            pool.map(mover, [primero["id"], segundo["id"]])
        )
    assert sorted(estados) == [200, 409], estados


# --- 9. Disponibilidad real y RBAC -----------------------------------------


def _disponibilidad(api_client, actor, profesional_id, **params):
    return api_client.get(
        f"/profesionales/{profesional_id}/disponibilidad",
        params={"fecha": str(FECHA_LUNES), **params},
        headers=bearer(actor),
    )


def test_disponibilidad_descuenta_turnos_activos(
    api_client, session_factory
) -> None:
    """Expected: an active turn removes its slot from the agenda."""
    base = _setup(session_factory)
    _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    respuesta = _disponibilidad(
        api_client, base["actores"]["recepcionista"], base["profesional"].id
    )
    assert respuesta.status_code == 200, respuesta.text
    inicios = [
        datetime.fromisoformat(slot["inicio"]) for slot in respuesta.json()
    ]
    assert inicios == [_hora(10), _hora(11)]


def test_cancelacion_libera_el_slot_en_disponibilidad(
    api_client, session_factory
) -> None:
    """Expected: a cancelled turn returns the slot."""
    base = _setup(session_factory)
    turno = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    _cambiar(
        api_client, base["actores"]["recepcionista"], turno["id"], "cancelado"
    )
    respuesta = _disponibilidad(
        api_client, base["actores"]["recepcionista"], base["profesional"].id
    )
    assert len(respuesta.json()) == 3


def test_turno_de_otro_profesional_no_afecta(
    api_client, session_factory
) -> None:
    """Edge: availability is per professional (and per chair when asked)."""
    base = _setup(session_factory)
    otro_profesional = run(
        create_profesional(
            session_factory, base["consultorio_id"], "MP-TURNOS-5"
        )
    )
    otro_sillon = run(
        create_sillon(session_factory, base["consultorio_id"], "Sillon D")
    )
    _crear(
        api_client,
        base["actores"]["recepcionista"],
        turno_payload(
            paciente_id=base["paciente"].id,
            profesional_id=otro_profesional.id,
            sillon_id=otro_sillon.id,
            inicio=_hora(9).isoformat(),
        ),
    )
    respuesta = _disponibilidad(
        api_client, base["actores"]["recepcionista"], base["profesional"].id
    )
    assert len(respuesta.json()) == 3


def test_dia_completo_devuelve_lista_vacia(api_client, session_factory) -> None:
    """Edge: with every slot taken the response is []."""
    base = _setup(session_factory)
    for hora in (9, 10, 11):
        _crear_ok(api_client, base, inicio=_hora(hora).isoformat())
    respuesta = _disponibilidad(
        api_client, base["actores"]["recepcionista"], base["profesional"].id
    )
    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_recepcion_opera_la_agenda(api_client, session_factory) -> None:
    """Expected: reception creates, moves and changes state."""
    base = _setup(session_factory)
    actor = base["actores"]["recepcionista"]
    turno = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    assert (
        _reprogramar(
            api_client, actor, turno["id"], {"inicio": _hora(10).isoformat()}
        ).status_code
        == 200
    )
    assert _cambiar(api_client, actor, turno["id"], "confirmado").status_code == 200


def test_odontologo_solo_opera_sus_turnos(api_client, session_factory) -> None:
    """Business error: ownership check on the professional link."""
    base = _setup(session_factory)
    propio = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    otro_profesional = run(
        create_profesional(
            session_factory, base["consultorio_id"], "MP-TURNOS-6"
        )
    )
    otro_sillon = run(
        create_sillon(session_factory, base["consultorio_id"], "Sillon E")
    )
    ajeno = _crear(
        api_client,
        base["actores"]["recepcionista"],
        turno_payload(
            paciente_id=base["paciente"].id,
            profesional_id=otro_profesional.id,
            sillon_id=otro_sillon.id,
            inicio=_hora(9).isoformat(),
        ),
    ).json()

    odontologo = base["actores"]["odontologo"]
    assert _cambiar(api_client, odontologo, propio["id"], "confirmado").status_code == 200
    assert _cambiar(api_client, odontologo, ajeno["id"], "confirmado").status_code == 403


def test_odontologo_no_crea_turnos(api_client, session_factory) -> None:
    """Business error: the matrix gives the dentist RU over own agenda."""
    base = _setup(session_factory)
    respuesta = _crear(
        api_client,
        base["actores"]["odontologo"],
        _payload(base, inicio=_hora(9).isoformat()),
    )
    assert respuesta.status_code == 403


@pytest.mark.parametrize("rol", ["asistente", "auditor"])
def test_asistente_y_auditor_solo_leen(
    api_client, session_factory, rol: str
) -> None:
    """Business error: read-only roles cannot mutate the agenda."""
    base = _setup(session_factory)
    turno = _crear_ok(api_client, base, inicio=_hora(9).isoformat())
    actor = base["actores"][rol]

    assert _listar(api_client, actor).status_code == 200
    assert (
        _crear(api_client, actor, _payload(base, inicio=_hora(10).isoformat())).status_code
        == 403
    )
    assert _cambiar(api_client, actor, turno["id"], "confirmado").status_code == 403
    assert (
        _reprogramar(
            api_client, actor, turno["id"], {"inicio": _hora(10).isoformat()}
        ).status_code
        == 403
    )


def test_turnos_sin_token_devuelve_401(api_client, session_factory) -> None:
    """Business error: the agenda is never public in C-06."""
    base = _setup(session_factory)
    assert api_client.get("/turnos", params=_semana(None)).status_code == 401
    assert api_client.post("/turnos", json=_payload(base)).status_code == 401
