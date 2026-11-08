"""C-15 reports RBAC and read-only guarantees (tasks 6.3/6.4, design D9/D10).

Admin and auditor read the four reports; reception reads agenda, absence and
cash but not settlements; the dentist reads their own agenda/absence/cash and
all settlements; the assistant has no access; a token is always required.
"""

from sqlalchemy import func, select

from app.models import (
    CajaDiaria,
    Cobro,
    LiquidacionObraSocial,
    RegistroAuditoria,
    Turno,
)
from tests.integration.helpers import run
from tests.integration.reportes_helpers import setup_rbac_reporte
from tests.integration.recursos_helpers import bearer

AGENDA = "/reportes/agenda"
AUSENTISMO = "/reportes/ausentismo"
CAJA = "/reportes/caja"
LIQUIDACIONES = "/reportes/liquidaciones"

PARAMS = {
    AGENDA: {"desde": "2026-11-09", "hasta": "2026-11-09"},
    AUSENTISMO: {"desde": "2026-11-09", "hasta": "2026-11-09"},
    CAJA: {"desde": "2026-11-01", "hasta": "2026-11-30"},
    LIQUIDACIONES: {"desde": "2026-11-01", "hasta": "2026-11-30"},
}


def _get(api_client, data, path: str, actor: str | None, **extra):
    headers = bearer(data["actores"][actor]) if actor else {}
    return api_client.get(
        path, params={**PARAMS[path], **extra}, headers=headers
    )


def test_matriz_completa_de_acceso(api_client, session_factory) -> None:
    data = run(setup_rbac_reporte(session_factory))

    esperado = {
        "administrador": {
            AGENDA: 200,
            AUSENTISMO: 200,
            CAJA: 200,
            LIQUIDACIONES: 200,
        },
        "odontologo": {
            AGENDA: 200,
            AUSENTISMO: 200,
            CAJA: 200,
            LIQUIDACIONES: 200,
        },
        "recepcionista": {
            AGENDA: 200,
            AUSENTISMO: 200,
            CAJA: 200,
            LIQUIDACIONES: 403,
        },
        "auditor": {
            AGENDA: 200,
            AUSENTISMO: 200,
            CAJA: 200,
            LIQUIDACIONES: 200,
        },
        "asistente": {
            AGENDA: 403,
            AUSENTISMO: 403,
            CAJA: 403,
            LIQUIDACIONES: 403,
        },
    }
    for actor, rutas in esperado.items():
        for path, codigo in rutas.items():
            respuesta = _get(api_client, data, path, actor)
            assert respuesta.status_code == codigo, (
                actor,
                path,
                respuesta.text,
            )


def test_sin_token_devuelve_401(api_client, session_factory) -> None:
    data = run(setup_rbac_reporte(session_factory))
    for path in (AGENDA, AUSENTISMO, CAJA, LIQUIDACIONES):
        respuesta = _get(api_client, data, path, None)
        assert respuesta.status_code == 401, (path, respuesta.text)


def test_odontologo_solo_sus_agregados_y_403_con_otro_profesional(
    api_client, session_factory
) -> None:
    data = run(setup_rbac_reporte(session_factory))
    propio = str(data["profesional"].id)
    ajeno = str(data["profesional_dos"].id)

    agenda = _get(api_client, data, AGENDA, "odontologo")
    assert agenda.status_code == 200, agenda.text
    cuerpo_agenda = agenda.json()
    assert cuerpo_agenda["total_turnos"] == 1
    assert {
        fila["profesional_id"]
        for fila in cuerpo_agenda["por_profesional"]
    } == {propio}
    assert {
        fila["profesional_id"] for fila in cuerpo_agenda["detalle"]
    } == {propio}

    ausentismo = _get(api_client, data, AUSENTISMO, "odontologo")
    assert ausentismo.status_code == 200, ausentismo.text
    assert ausentismo.json()["atendidos"] == 1
    assert {
        fila["profesional_id"]
        for fila in ausentismo.json()["por_profesional"]
    } == {propio}

    caja = _get(api_client, data, CAJA, "odontologo")
    assert caja.status_code == 200, caja.text
    cuerpo_caja = caja.json()
    assert cuerpo_caja["total_aprobado"] == "1000.00"
    assert cuerpo_caja["total_detalle"] == 1
    assert {
        fila["cobro_id"] for fila in cuerpo_caja["detalle"]
    } == {str(data["cobros"]["propio"])}

    assert (
        _get(api_client, data, AGENDA, "odontologo", profesional_id=ajeno)
        .status_code
        == 403
    )
    assert (
        _get(
            api_client,
            data,
            AUSENTISMO,
            "odontologo",
            profesional_id=ajeno,
        ).status_code
        == 403
    )
    # Caja declares no `profesional_id` (D13): the strict boundary answers 422.
    assert (
        _get(api_client, data, CAJA, "odontologo", profesional_id=ajeno)
        .status_code
        == 422
    )

    admin = _get(api_client, data, AGENDA, "administrador", profesional_id=ajeno)
    assert admin.status_code == 200, admin.text
    assert admin.json()["total_turnos"] == 1


def test_lectura_no_audita_ni_modifica_filas(
    api_client, session_factory
) -> None:
    data = run(setup_rbac_reporte(session_factory))

    async def contar() -> dict[str, int]:
        async with session_factory() as session:
            return {
                "auditoria": int(
                    await session.scalar(
                        select(func.count()).select_from(RegistroAuditoria)
                    )
                    or 0
                ),
                "turnos": int(
                    await session.scalar(
                        select(func.count()).select_from(Turno)
                    )
                    or 0
                ),
                "cobros": int(
                    await session.scalar(
                        select(func.count()).select_from(Cobro)
                    )
                    or 0
                ),
                "cajas": int(
                    await session.scalar(
                        select(func.count()).select_from(CajaDiaria)
                    )
                    or 0
                ),
                "liquidaciones": int(
                    await session.scalar(
                        select(func.count()).select_from(
                            LiquidacionObraSocial
                        )
                    )
                    or 0
                ),
            }

    antes = run(contar())
    for path in (AGENDA, AUSENTISMO, CAJA, LIQUIDACIONES):
        for actor in ("administrador", "auditor"):
            respuesta = _get(api_client, data, path, actor)
            assert respuesta.status_code == 200, (path, respuesta.text)
    despues = run(contar())

    assert despues == antes
    assert despues["auditoria"] == 0
