"""Regression: the public reservation contract does not require privacy acceptance.

C-16 publishes the policy but must not change C-07: a valid body without any
privacy field is 201, an extra privacy field is still 422, and no acceptance
table/event is created. This test fails if someone reintroduces the requirement.
"""

from datetime import datetime

import pytest
from sqlalchemy import func, select, text

from app.domain.agenda import ARGENTINA_OFFSET
from app.models import Turno
from tests.integration.helpers import run
from tests.integration.recursos_helpers import (
    consultorio_demo_id,
    create_profesional,
    seed_demo,
)
from tests.integration.turnos_helpers import prestacion_id


def _setup(session_factory) -> dict[str, object]:
    run(seed_demo(session_factory))
    consultorio_id = run(consultorio_demo_id(session_factory))
    profesional = run(
        create_profesional(session_factory, consultorio_id, "MP-PRIV-1")
    )
    return {
        "consultorio_id": consultorio_id,
        "profesional": profesional,
        "cons": run(prestacion_id(session_factory, "CONS")),
    }


def _payload(base: dict[str, object], **overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "nombre": "Contrato",
        "apellido": "Demo",
        "dni": "43000911",
        "telefono": "11 7777-1111",
        "email": "contrato.demo@example.test",
        "profesional_id": str(base["profesional"].id),
        "prestacion_id": str(base["cons"]),
        "inicio": datetime(
            2026, 11, 9, 9, 0, tzinfo=ARGENTINA_OFFSET
        ).isoformat(),
    }
    payload.update(overrides)
    return payload


def _contar_turnos(session_factory) -> int:
    async def contar() -> int:
        async with session_factory() as session:
            return int(
                await session.scalar(
                    select(func.count()).select_from(Turno)
                )
                or 0
            )

    return run(contar())


def test_reserva_valida_sin_campos_de_privacidad_es_201(
    api_client, session_factory
) -> None:
    base = _setup(session_factory)
    response = api_client.post("/reservar/demo/turnos", json=_payload(base))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["estado"] == "reservado"
    assert "acepta_privacidad" not in body
    assert "politica_version" not in body
    assert _contar_turnos(session_factory) == 1


def test_campo_extra_de_privacidad_sigue_siendo_422(
    api_client, session_factory
) -> None:
    base = _setup(session_factory)
    for extra in (
        {"acepta_privacidad": True},
        {"politica_version": "v1-2026-11"},
    ):
        response = api_client.post(
            "/reservar/demo/turnos", json=_payload(base, **extra)
        )
        assert response.status_code == 422, (extra, response.text)
    assert _contar_turnos(session_factory) == 0


def test_no_se_crea_tabla_ni_evento_de_aceptacion(
    api_client, session_factory
) -> None:
    base = _setup(session_factory)
    assert (
        api_client.post("/reservar/demo/turnos", json=_payload(base)).status_code
        == 201
    )

    async def esquema() -> tuple[set[str], set[str]]:
        async with session_factory() as session:
            tablas = set(
                await session.scalars(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                )
            )
            columnas = set(
                await session.scalars(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public'"
                    )
                )
            )
            return tablas, columnas

    tablas, columnas = run(esquema())
    assert not {t for t in tablas if "privacidad" in t or "acepta" in t}
    assert not {
        c
        for c in columnas
        if "privacidad" in c or "acepta_privacidad" in c
    }

    async def acciones() -> list[str]:
        async with session_factory() as session:
            return list(
                await session.scalars(
                    text("SELECT accion FROM registro_auditoria")
                )
            )

    assert not [
        accion for accion in run(acciones()) if "privacidad" in accion
    ]


def test_publicar_la_politica_no_bloquea_la_reserva(
    api_client, session_factory
) -> None:
    base = _setup(session_factory)
    assert api_client.get("/privacidad").status_code == 200
    response = api_client.post("/reservar/demo/turnos", json=_payload(base))
    assert response.status_code == 201, response.text
