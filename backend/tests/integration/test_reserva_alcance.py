"""Minimum-privilege scope of the patient's management link (C-16, task 7.4).

One `gestion_turno` token per appointment: it only resolves its own turn and
catalog data. There is no public listing, tokens never cross turns, and the
payload never carries the patient's name, DNI, phone or email.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.domain.agenda import ARGENTINA_OFFSET
from app.infrastructure.tokens import create_single_use_token, hash_token
from app.models import TokenUnSoloUso
from tests.integration.recursos_helpers import (
    consultorio_demo_id,
    create_profesional,
    seed_demo,
)
from tests.integration.turnos_helpers import prestacion_id

_NOMBRE = "NombreSecretoPaciente"
_APELLIDO = "ApellidoSecretoPaciente"
_DNI = "43000999"
_TELEFONO = "11 7777-8888"
_TELEFONO_NORMALIZADO = "+5491177778888"
_EMAIL = "secreto.paciente@example.test"

_KEYS_GESTION = {
    "turno_id",
    "inicio",
    "fin",
    "estado",
    "profesional",
    "prestacion",
    "sena",
    "puede_confirmar",
    "puede_cancelar",
    "plazo_cancelacion_horas",
    "politica_sena",
}


async def _setup(session_factory) -> dict[str, object]:
    await seed_demo(session_factory)
    consultorio_id = await consultorio_demo_id(session_factory)
    profesional = await create_profesional(
        session_factory, consultorio_id, "MP-ALC-1"
    )
    return {
        "consultorio_id": consultorio_id,
        "profesional": profesional,
        "cons": await prestacion_id(session_factory, "CONS"),
    }


def _payload(base: dict[str, object], hora: int) -> dict[str, object]:
    return {
        "nombre": _NOMBRE,
        "apellido": _APELLIDO,
        "dni": _DNI,
        "telefono": _TELEFONO,
        "email": _EMAIL,
        "profesional_id": str(base["profesional"].id),
        "prestacion_id": str(base["cons"]),
        "inicio": datetime(
            2026, 11, 9, hora, 0, tzinfo=ARGENTINA_OFFSET
        ).isoformat(),
    }


def _reservar(api_client, base: dict[str, object], hora: int) -> dict:
    response = api_client.post(
        "/reservar/demo/turnos", json=_payload(base, hora)
    )
    assert response.status_code == 201, response.text
    return response.json()


def _token(body: dict) -> str:
    return str(body["gestion_url"]).rsplit("/", 1)[-1]


def _sin_pii(texto: str) -> None:
    bajo = texto.lower()
    for secreto in (
        _NOMBRE,
        _APELLIDO,
        _DNI,
        _TELEFONO_NORMALIZADO,
        _EMAIL,
    ):
        assert secreto.lower() not in bajo, secreto


@pytest.mark.anyio
async def test_cada_token_muestra_solo_su_turno_sin_pii(
    api_client, session_factory
) -> None:
    base = await _setup(session_factory)
    turno_a = _reservar(api_client, base, 9)
    turno_b = _reservar(api_client, base, 10)
    token_a = _token(turno_a)
    token_b = _token(turno_b)
    assert token_a != token_b
    assert turno_a["turno_id"] != turno_b["turno_id"]

    respuesta_a = api_client.get(f"/reservar/gestion/{token_a}")
    respuesta_b = api_client.get(f"/reservar/gestion/{token_b}")
    assert respuesta_a.status_code == 200, respuesta_a.text
    assert respuesta_b.status_code == 200, respuesta_b.text

    assert respuesta_a.json()["turno_id"] == turno_a["turno_id"]
    assert respuesta_b.json()["turno_id"] == turno_b["turno_id"]
    assert turno_b["turno_id"] not in respuesta_a.text
    assert turno_a["turno_id"] not in respuesta_b.text
    assert token_b not in respuesta_a.text
    assert token_a not in respuesta_b.text

    for respuesta in (respuesta_a, respuesta_b):
        assert set(respuesta.json()) == _KEYS_GESTION
        _sin_pii(respuesta.text)


@pytest.mark.anyio
async def test_token_a_no_lee_ni_modifica_el_turno_b(
    api_client, session_factory
) -> None:
    base = await _setup(session_factory)
    turno_a = _reservar(api_client, base, 9)
    turno_b = _reservar(api_client, base, 10)
    token_a = _token(turno_a)

    # The token does not accept a target turn: an extra parameter is rejected.
    intruso = api_client.get(
        f"/reservar/gestion/{token_a}",
        params={"turno_id": turno_b["turno_id"]},
    )
    assert intruso.status_code == 422

    assert (
        api_client.post(f"/reservar/gestion/{token_a}/cancelar").status_code
        == 200
    )
    assert api_client.get(f"/reservar/gestion/{token_a}").status_code == 410

    # Turn B is untouched and still readable with its own token.
    respuesta_b = api_client.get(f"/reservar/gestion/{_token(turno_b)}")
    assert respuesta_b.status_code == 200, respuesta_b.text
    assert respuesta_b.json()["turno_id"] == turno_b["turno_id"]
    assert respuesta_b.json()["estado"] == "reservado"


@pytest.mark.anyio
async def test_no_existe_listado_publico_de_turnos(
    api_client, session_factory
) -> None:
    base = await _setup(session_factory)
    turno = _reservar(api_client, base, 9)

    assert api_client.get("/reservar/demo/turnos").status_code == 405
    assert api_client.get("/reservar/turnos").status_code == 404
    assert api_client.get("/reservar/gestion").status_code == 404

    catalogo = api_client.get("/reservar/demo")
    assert catalogo.status_code == 200
    assert "turnos" not in catalogo.json()
    assert turno["turno_id"] not in catalogo.text


@pytest.mark.anyio
async def test_token_usado_vencido_o_de_otro_proposito_410(
    api_client, session_factory
) -> None:
    base = await _setup(session_factory)
    turno_a = _reservar(api_client, base, 9)
    token_a = _token(turno_a)
    assert (
        api_client.post(f"/reservar/gestion/{token_a}/cancelar").status_code
        == 200
    )
    assert api_client.get(f"/reservar/gestion/{token_a}").status_code == 410

    turno_c = _reservar(api_client, base, 10)
    token_c = _token(turno_c)

    async def vencer() -> None:
        async with session_factory() as session, session.begin():
            registro = await session.scalar(
                select(TokenUnSoloUso).where(
                    TokenUnSoloUso.token_hash == hash_token(token_c)
                )
            )
            assert registro is not None
            registro.expira_at = datetime.now(timezone.utc) - timedelta(
                minutes=1
            )

    await vencer()
    assert api_client.get(f"/reservar/gestion/{token_c}").status_code == 410

    async def otro_proposito() -> str:
        async with session_factory() as session, session.begin():
            emitido = await create_single_use_token(
                session,
                tipo="recordatorio",
                entidad_tipo="turno",
                entidad_id=str(uuid.UUID(turno_c["turno_id"])),
            )
            return emitido.token

    token_ajeno = await otro_proposito()
    assert (
        api_client.get(f"/reservar/gestion/{token_ajeno}").status_code == 410
    )
    assert api_client.get("/reservar/gestion/no-existe").status_code == 410
