"""C-14 group 10.3: settlement/coverage RBAC matrix (D11)."""

from datetime import date

from tests.integration.helpers import run
from tests.integration.liquidaciones_helpers import (
    crear_escenario,
    get_cobertura,
    post_liquidacion,
    setup_liquidaciones,
)
from tests.integration.recursos_helpers import bearer


def _setup(session_factory) -> dict[str, object]:
    return run(setup_liquidaciones(session_factory))


def _crear_liquidacion(api_client, session_factory, data) -> dict[str, object]:
    run(crear_escenario(session_factory, data))
    respuesta = post_liquidacion(api_client, data)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def test_lectura_para_los_cuatro_roles(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    liquidacion = _crear_liquidacion(api_client, session_factory, data)
    for actor in (
        "administrador",
        "recepcionista",
        "odontologo",
        "auditor",
    ):
        headers = bearer(data["actores"][actor])
        assert (
            api_client.get(
                "/obras-sociales/liquidaciones", headers=headers
            ).status_code
            == 200
        ), actor
        assert (
            api_client.get(
                f"/obras-sociales/liquidaciones/{liquidacion['id']}",
                headers=headers,
            ).status_code
            == 200
        ), actor


def test_alta_solo_administrador(api_client, session_factory) -> None:
    data = _setup(session_factory)
    for actor in ("recepcionista", "odontologo", "asistente"):
        respuesta = post_liquidacion(api_client, data, actor=actor)
        assert respuesta.status_code == 403, (actor, respuesta.text)

    run(crear_escenario(session_factory, data))
    admin = post_liquidacion(api_client, data)
    assert admin.status_code == 201, admin.text


def test_cierre_y_borrado_solo_administrador(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    liquidacion = _crear_liquidacion(api_client, session_factory, data)
    for actor in ("recepcionista", "odontologo", "asistente"):
        assert (
            api_client.post(
                f"/obras-sociales/liquidaciones/{liquidacion['id']}/cerrar",
                headers=bearer(data["actores"][actor]),
            ).status_code
            == 403
        ), actor
        assert (
            api_client.delete(
                f"/obras-sociales/liquidaciones/{liquidacion['id']}",
                headers=bearer(data["actores"][actor]),
            ).status_code
            == 403
        ), actor

    cierre = api_client.post(
        f"/obras-sociales/liquidaciones/{liquidacion['id']}/cerrar",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert cierre.status_code == 200, cierre.text

    borrador_escenario = run(
        crear_escenario(
            session_factory,
            data,
            fecha_cobro=date(2026, 12, 5),
        )
    )
    assert borrador_escenario["cobro_id"] is not None
    borrador = post_liquidacion(
        api_client,
        data,
        desde=date(2026, 12, 1),
        hasta=date(2026, 12, 31),
    )
    assert borrador.status_code == 201, borrador.text
    borrado = api_client.delete(
        f"/obras-sociales/liquidaciones/{borrador.json()['id']}",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert borrado.status_code == 204, borrado.text


def test_observaciones_administrador_y_recepcion(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    liquidacion = _crear_liquidacion(api_client, session_factory, data)

    for actor in ("odontologo", "asistente"):
        respuesta = api_client.put(
            f"/obras-sociales/liquidaciones/{liquidacion['id']}",
            json={"observaciones": "no autorizado"},
            headers=bearer(data["actores"][actor]),
        )
        assert respuesta.status_code == 403, (actor, respuesta.text)

    for actor in ("administrador", "recepcionista"):
        respuesta = api_client.put(
            f"/obras-sociales/liquidaciones/{liquidacion['id']}",
            json={"observaciones": f"por {actor}"},
            headers=bearer(data["actores"][actor]),
        )
        assert respuesta.status_code == 200, (actor, respuesta.text)
        assert respuesta.json()["observaciones"] == f"por {actor}"


def test_cobertura_lectura_y_sin_token(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    for actor in (
        "administrador",
        "recepcionista",
        "odontologo",
        "auditor",
    ):
        respuesta = get_cobertura(
            api_client,
            data,
            paciente_id=data["paciente_os_demo"].id,
            prestacion_id=data["prestaciones"]["CONS"].id,
            actor=actor,
        )
        assert respuesta.status_code == 200, (actor, respuesta.text)

    asistente = get_cobertura(
        api_client,
        data,
        paciente_id=data["paciente_os_demo"].id,
        prestacion_id=data["prestaciones"]["CONS"].id,
        actor="asistente",
    )
    assert asistente.status_code == 403, asistente.text

    sin_token = api_client.get(
        "/obras-sociales/cobertura",
        params={
            "paciente_id": str(data["paciente_os_demo"].id),
            "prestacion_id": str(data["prestaciones"]["CONS"].id),
        },
    )
    assert sin_token.status_code == 401, sin_token.text


def test_liquidaciones_sin_token_devuelve_401(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    liquidacion = _crear_liquidacion(api_client, session_factory, data)
    assert (
        api_client.get("/obras-sociales/liquidaciones").status_code == 401
    )
    assert (
        api_client.get(
            f"/obras-sociales/liquidaciones/{liquidacion['id']}"
        ).status_code
        == 401
    )
    assert (
        api_client.post(
            "/obras-sociales/liquidaciones",
            json={
                "obra_social_id": str(data["obra_social_demo_id"]),
                "desde": date(2026, 11, 1).isoformat(),
                "hasta": date(2026, 11, 30).isoformat(),
            },
        ).status_code
        == 401
    )
    assert (
        api_client.post(
            f"/obras-sociales/liquidaciones/{liquidacion['id']}/cerrar"
        ).status_code
        == 401
    )
    assert (
        api_client.delete(
            f"/obras-sociales/liquidaciones/{liquidacion['id']}"
        ).status_code
        == 401
    )
