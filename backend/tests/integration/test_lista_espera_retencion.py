"""Retention of a freed slot: availability, 409s, expiry and conversion (C-10).

Task 3.1 (red first): while an offer is live the slot must disappear from both
availability views and every booking path must answer 409, including sobreturnos
and the public flow. An expired retention stops blocking on its own, back-to-back
turns still fit, and converting releases the retention.
"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.domain.agenda import ARGENTINA_OFFSET
from app.models import Paciente, Turno
from tests.integration.helpers import run, sqlstate
from tests.integration.lista_espera_helpers import (
    contar_estado,
    convertir_entrada,
    insertar_entrada,
    vencer_entrada,
)
from tests.integration.recursos_helpers import (
    bearer,
    create_profesional,
    create_sillon,
)
from tests.integration.turnos_helpers import (
    insertar_turno_db,
    prestacion_id,
    setup_turnos,
    turno_payload,
)

FECHA = "2026-11-09"


def _hora(hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 11, 9, hora, minuto, tzinfo=ARGENTINA_OFFSET)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _setup(session_factory) -> dict[str, object]:
    base = run(setup_turnos(session_factory))
    base["cons"] = run(prestacion_id(session_factory, "CONS"))
    return base


def _retener(
    base,
    session_factory,
    *,
    inicio: datetime | None = None,
    fin: datetime | None = None,
    expira: datetime | None = None,
    profesional=None,
    sillon=None,
) -> uuid.UUID:
    """Insert an entry already in `ofrecido` over the given interval."""
    inicio = inicio or _hora(9)
    fin = fin or inicio + timedelta(hours=1)
    expira = expira if expira is not None else _ahora() + timedelta(minutes=30)
    return run(
        insertar_entrada(
            session_factory,
            consultorio_id=base["consultorio_id"],
            paciente_id=base["paciente"].id,
            prestacion_id=base["cons"],
            estado="ofrecido",
            oferta_profesional_id=(profesional or base["profesional"]).id,
            oferta_sillon_id=(sillon or base["sillon"]).id,
            oferta_inicio=inicio,
            oferta_fin=fin,
            oferta_expira_en=expira,
        )
    )


def _crear(api_client, base, **overrides):
    return api_client.post(
        "/turnos",
        json=turno_payload(
            paciente_id=base["paciente"].id,
            profesional_id=base["profesional"].id,
            sillon_id=base["sillon"].id,
            **overrides,
        ),
        headers=bearer(base["actores"]["recepcionista"]),
    )


def _disponibilidad(api_client, base, **params):
    return api_client.get(
        f"/profesionales/{base['profesional'].id}/disponibilidad",
        params={"fecha": FECHA, **params},
        headers=bearer(base["actores"]["recepcionista"]),
    )


def _disponibilidad_publica(api_client, base):
    return api_client.get(
        "/reservar/demo/disponibilidad",
        params={
            "fecha": FECHA,
            "profesional_id": str(base["profesional"].id),
            "prestacion_id": str(base["cons"]),
        },
    )


def _inicios(respuesta) -> list[str]:
    return [slot["inicio"][11:16] for slot in respuesta.json()]


def _reserva_publica(api_client, base, **overrides):
    payload: dict[str, object] = {
        "nombre": "Lista",
        "apellido": "Espera",
        "dni": "43555111",
        "telefono": "11 4444-5555",
        "email": "lista.espera@example.test",
        "profesional_id": str(base["profesional"].id),
        "prestacion_id": str(base["cons"]),
        "inicio": _hora(9).isoformat(),
    }
    payload.update(overrides)
    return api_client.post("/reservar/demo/turnos", json=payload)


def _contar_dni(session_factory, dni: str) -> int:
    async def contar() -> int:
        async with session_factory() as session:
            return await session.scalar(
                select(func.count())
                .select_from(Paciente)
                .where(Paciente.dni == dni)
            )

    return run(contar())


# --- Disponibilidad ---------------------------------------------------------


def test_retencion_vigente_oculta_el_slot_en_el_backoffice(
    api_client, session_factory
) -> None:
    """Expected: a live offer removes the retained interval from the agenda."""
    base = _setup(session_factory)
    _retener(base, session_factory)

    respuesta = _disponibilidad(api_client, base)
    assert respuesta.status_code == 200, respuesta.text
    assert _inicios(respuesta) == ["10:00", "11:00"]


def test_retencion_vigente_oculta_el_slot_en_la_disponibilidad_publica(
    api_client, session_factory
) -> None:
    """Expected: the public view hides the retained slot too (no JWT)."""
    base = _setup(session_factory)
    _retener(base, session_factory)

    respuesta = _disponibilidad_publica(api_client, base)
    assert respuesta.status_code == 200, respuesta.text
    assert _inicios(respuesta) == ["10:00", "10:30", "11:00", "11:30"]


def test_retencion_vencida_sin_barrido_no_oculta_ni_bloquea(
    api_client, session_factory
) -> None:
    """Edge: lazy expiry — the slot is bookable before the worker sweeps."""
    base = _setup(session_factory)
    _retener(base, session_factory, expira=_ahora() - timedelta(minutes=1))

    assert _inicios(_disponibilidad(api_client, base)) == [
        "09:00",
        "10:00",
        "11:00",
    ]
    assert len(_disponibilidad_publica(api_client, base).json()) == 6
    assert _crear(api_client, base, inicio=_hora(9).isoformat()).status_code == 201


# --- Alta, reprogramación y reserva pública ---------------------------------


def test_alta_que_se_solapa_con_una_retencion_devuelve_409(
    api_client, session_factory
) -> None:
    """Business error: the retention is a resource, not only a hidden slot."""
    base = _setup(session_factory)
    _retener(base, session_factory)

    respuesta = _crear(api_client, base, inicio=_hora(9).isoformat())
    assert respuesta.status_code == 409, respuesta.text
    assert "retenid" in respuesta.json()["detail"].lower()


def test_sobreturno_marcado_contra_una_retencion_devuelve_409(
    api_client, session_factory
) -> None:
    """Business error: the sobreturno mark does not allow stepping on an offer."""
    base = _setup(session_factory)
    _retener(base, session_factory)

    respuesta = _crear(
        api_client,
        base,
        inicio=_hora(9, 30).isoformat(),
        es_sobreturno=True,
        color_sobreturno="#F97316",
    )
    assert respuesta.status_code == 409, respuesta.text


def test_turno_consecutivo_en_el_borde_se_permite(
    api_client, session_factory
) -> None:
    """Edge: half-open intervals — starting when the offer ends is free."""
    base = _setup(session_factory)
    _retener(base, session_factory)

    assert _crear(api_client, base, inicio=_hora(10).isoformat()).status_code == 201


def test_retencion_de_otro_recurso_no_afecta(
    api_client, session_factory
) -> None:
    """Edge: another professional and chair at the same time does not block."""
    base = _setup(session_factory)
    otro_profesional = run(
        create_profesional(
            session_factory, base["consultorio_id"], "MP-RET-OTRO"
        )
    )
    otro_sillon = run(
        create_sillon(session_factory, base["consultorio_id"], "Sillon RET")
    )
    _retener(
        base,
        session_factory,
        profesional=otro_profesional,
        sillon=otro_sillon,
    )

    assert _crear(api_client, base, inicio=_hora(9).isoformat()).status_code == 201


def test_reprogramacion_hacia_un_horario_retenido_devuelve_409(
    api_client, session_factory
) -> None:
    """Business error: the move is rejected and the original row keeps its data."""
    base = _setup(session_factory)
    turno = _crear(api_client, base, inicio=_hora(10).isoformat())
    assert turno.status_code == 201, turno.text
    _retener(base, session_factory)

    respuesta = api_client.patch(
        f"/turnos/{turno.json()['id']}/reprogramar",
        json={"inicio": _hora(9).isoformat()},
        headers=bearer(base["actores"]["recepcionista"]),
    )
    assert respuesta.status_code == 409, respuesta.text

    ficha = api_client.get(
        f"/turnos/{turno.json()['id']}",
        headers=bearer(base["actores"]["recepcionista"]),
    )
    assert datetime.fromisoformat(ficha.json()["inicio"]) == _hora(10)


def test_reserva_publica_sobre_una_retencion_devuelve_409_sin_residuos(
    api_client, session_factory
) -> None:
    """Business error: no patient and no turn are created by the failed booking."""
    base = _setup(session_factory)
    _retener(base, session_factory)

    respuesta = _reserva_publica(api_client, base)
    assert respuesta.status_code == 409, respuesta.text
    assert _contar_dni(session_factory, "43555111") == 0

    async def contar_turnos() -> int:
        async with session_factory() as session:
            return await session.scalar(
                select(func.count()).select_from(Turno)
            )

    assert run(contar_turnos()) == 0


# --- Conversión y concurrencia ----------------------------------------------


def test_conversion_libera_la_retencion_y_el_turno_pasa_a_bloquear(
    api_client, session_factory
) -> None:
    """Expected: after converting, the created turn is the only blocker."""
    base = _setup(session_factory)
    entrada_id = _retener(base, session_factory)
    turno_id = run(
        insertar_turno_db(
            session_factory,
            consultorio_id=base["consultorio_id"],
            paciente_id=base["paciente"].id,
            profesional_id=base["profesional"].id,
            sillon_id=base["sillon"].id,
            inicio=_hora(9),
            fin=_hora(10),
        )
    )
    run(convertir_entrada(session_factory, entrada_id, turno_id))
    assert run(contar_estado(session_factory, "ofrecido")) == 0

    # The turn now hides the slot and rejects the overlap.
    assert _inicios(_disponibilidad(api_client, base)) == ["10:00", "11:00"]
    assert _crear(api_client, base, inicio=_hora(9).isoformat()).status_code == 409

    # Cancelling the turn frees the slot: no retention survived the conversion.
    assert (
        api_client.patch(
            f"/turnos/{turno_id}/estado",
            json={"estado": "cancelado"},
            headers=bearer(base["actores"]["recepcionista"]),
        ).status_code
        == 200
    )
    assert _crear(api_client, base, inicio=_hora(9).isoformat()).status_code == 201


def test_retencion_vencida_marcada_por_el_barrido_libera_el_slot(
    api_client, session_factory
) -> None:
    """Edge: expiring the entry removes it from the exclusion index."""
    base = _setup(session_factory)
    entrada_id = _retener(base, session_factory)
    run(vencer_entrada(session_factory, entrada_id))

    assert len(_disponibilidad(api_client, base).json()) == 3
    assert _crear(api_client, base, inicio=_hora(9).isoformat()).status_code == 201


def test_dos_retenciones_solapadas_por_profesional_violan_la_exclusion(
    session_factory,
) -> None:
    """Business error at the DB level: two offers cannot hold the same range."""
    base = _setup(session_factory)
    _retener(base, session_factory)

    with pytest.raises(IntegrityError) as error:
        _retener(
            base,
            session_factory,
            inicio=_hora(9, 30),
            fin=_hora(10, 30),
        )
    assert sqlstate(error.value) == "23P01"


def test_dos_retenciones_solapadas_por_sillon_violan_la_exclusion(
    session_factory,
) -> None:
    """Business error at the DB level: the chair is an exclusion resource too."""
    base = _setup(session_factory)
    _retener(base, session_factory)
    otro_profesional = run(
        create_profesional(
            session_factory, base["consultorio_id"], "MP-RET-SILLON"
        )
    )

    with pytest.raises(IntegrityError) as error:
        _retener(
            base,
            session_factory,
            inicio=_hora(9, 30),
            fin=_hora(10, 30),
            profesional=otro_profesional,
        )
    assert sqlstate(error.value) == "23P01"


def test_dos_retenciones_concurrentes_dejan_una_sola(session_factory) -> None:
    """Edge: real concurrency — exactly one retention wins the range.

    With two exclusion constraints on the same pair of resources, PostgreSQL may
    resolve the race with a deadlock (40P01) instead of an exclusion violation
    (23P01): both transactions hold their own speculative insert and wait for the
    other. Either way only one offer survives, and slice 4 must translate both
    SQLSTATEs as "hueco ya retenido" (design D4 risk).
    """
    base = _setup(session_factory)

    def intentar(_: int) -> str:
        try:
            _retener(base, session_factory)
        except DBAPIError as error:
            return sqlstate(error) or "error"
        return "ok"

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(intentar, range(2)))

    assert resultados.count("ok") == 1, resultados
    perdedor = next(resultado for resultado in resultados if resultado != "ok")
    assert perdedor in {"23P01", "40P01"}, resultados
    assert run(contar_estado(session_factory, "ofrecido")) == 1
