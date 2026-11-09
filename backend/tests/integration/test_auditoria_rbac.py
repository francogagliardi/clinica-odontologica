"""RBAC of the audit viewer and read-only auditor (C-16, task 5.3/5.4).

Admin and auditor read the same history; dentist, reception and assistant get
403; no token gets 401. The auditor is read-only across users, roles, agenda,
clinical record, cash and exportations: every mutation is 403 and no domain or
audit row changes. A read does not append a row.
"""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    Cobro,
    Exportacion,
    HistoriaClinica,
    Turno,
    Usuario,
)
from tests.integration.auditoria_helpers import (
    contar_auditoria,
    insertar_auditoria,
)
from tests.integration.helpers import run
from tests.integration.recursos_helpers import bearer
from tests.integration.turnos_helpers import (
    INICIO,
    prestacion_id,
    setup_turnos,
    turno_payload,
)

URL = "/auditoria"


@pytest.fixture
def base(session_factory) -> dict:
    return run(setup_turnos(session_factory))


def _headers(usuario) -> dict[str, str]:
    return bearer(usuario)


async def _conteos(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[int, ...]:
    async with session_factory() as session:
        resultados: list[int] = []
        for model in (
            Usuario,
            Turno,
            HistoriaClinica,
            Cobro,
            Exportacion,
        ):
            total = await session.scalar(
                select(func.count()).select_from(model)
            )
            resultados.append(int(total or 0))
        return tuple(resultados)


@pytest.mark.anyio
async def test_admin_y_auditor_leen_y_el_resto_no(
    api_client, base, session_factory
) -> None:
    await insertar_auditoria(
        session_factory,
        [
            (
                uuid.uuid4(),
                base["actores"]["administrador"].id,
                "usuario.crear",
                "usuario",
                "u-1",
                INICIO,
            )
        ],
    )
    admin = api_client.get(
        URL, headers=_headers(base["actores"]["administrador"])
    )
    auditor = api_client.get(URL, headers=_headers(base["actores"]["auditor"]))
    assert admin.status_code == 200, admin.text
    assert auditor.status_code == 200, auditor.text
    assert admin.json() == auditor.json()

    for rol in ("odontologo", "recepcionista", "asistente"):
        response = api_client.get(URL, headers=_headers(base["actores"][rol]))
        assert response.status_code == 403, (rol, response.text)

    assert api_client.get(URL).status_code == 401


@pytest.mark.anyio
async def test_auditor_no_escribe_en_ningun_dominio(
    api_client, base, session_factory
) -> None:
    auditor = base["actores"]["auditor"]
    headers = _headers(auditor)
    prestacion = await prestacion_id(session_factory, "CONS")
    payload_turno = turno_payload(
        paciente_id=base["paciente"].id,
        profesional_id=base["profesional"].id,
        sillon_id=base["sillon"].id,
        prestacion_id=prestacion,
    )
    antes = await _conteos(session_factory)
    auditoria_antes = await contar_auditoria(session_factory)

    mutaciones = [
        (
            "post",
            "/usuarios",
            {
                "nombre": "No Permitido",
                "email": "no.permitido@clinica.test",
                "password": "clave-larga-123",
                "roles": ["odontologo"],
            },
        ),
        ("put", f"/usuarios/{auditor.id}/roles", {"roles": ["auditor"]}),
        ("post", "/turnos", payload_turno),
        (
            "post",
            "/historia-clinica",
            {"paciente_id": str(base["paciente"].id)},
        ),
        (
            "post",
            "/cobros",
            {
                "paciente_id": str(base["paciente"].id),
                "tipo": "otro",
                "medio": "efectivo",
                "monto": "1000.00",
            },
        ),
        ("post", "/exportaciones", {"alcance": "consultorio"}),
    ]

    for metodo, url, payload in mutaciones:
        response = getattr(api_client, metodo)(
            url, json=payload, headers=headers
        )
        assert response.status_code == 403, (url, response.text)

    assert await _conteos(session_factory) == antes
    assert await contar_auditoria(session_factory) == auditoria_antes


@pytest.mark.anyio
async def test_lectura_del_auditor_no_agrega_filas(
    api_client, base, session_factory
) -> None:
    await insertar_auditoria(
        session_factory,
        [
            (
                uuid.uuid4(),
                base["actores"]["administrador"].id,
                "usuario.crear",
                "usuario",
                "u-1",
                INICIO,
            )
        ],
    )
    antes = await contar_auditoria(session_factory)
    for _ in range(3):
        assert (
            api_client.get(
                URL, headers=_headers(base["actores"]["auditor"])
            ).status_code
            == 200
        )
    assert await contar_auditoria(session_factory) == antes
