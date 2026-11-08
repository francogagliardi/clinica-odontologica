"""C-14 group 9.5: draft/closed states, closing and soft delete (D9)."""

import uuid

from tests.integration.clinica_helpers import auditorias
from tests.integration.helpers import run
from tests.integration.liquidaciones_helpers import (
    contar_liquidaciones,
    crear_escenario,
    items_de,
    leer_liquidacion,
    post_liquidacion,
    setup_liquidaciones,
)
from tests.integration.recursos_helpers import bearer


def _setup(session_factory) -> dict[str, object]:
    return run(setup_liquidaciones(session_factory))


def _crear(api_client, session_factory, data) -> dict[str, object]:
    run(crear_escenario(session_factory, data))
    respuesta = post_liquidacion(api_client, data)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _cerrar(api_client, data, liquidacion_id, *, actor="administrador"):
    return api_client.post(
        f"/obras-sociales/liquidaciones/{liquidacion_id}/cerrar",
        headers=bearer(data["actores"][actor]),
    )


def _editar(api_client, data, liquidacion_id, *, actor="administrador"):
    return api_client.put(
        f"/obras-sociales/liquidaciones/{liquidacion_id}",
        json={"observaciones": "Observación de cierre"},
        headers=bearer(data["actores"][actor]),
    )


def _borrar(api_client, data, liquidacion_id, *, actor="administrador"):
    return api_client.delete(
        f"/obras-sociales/liquidaciones/{liquidacion_id}",
        headers=bearer(data["actores"][actor]),
    )


def test_cierre_congela_totales(api_client, session_factory) -> None:
    data = _setup(session_factory)
    creada = _crear(api_client, session_factory, data)

    respuesta = _cerrar(api_client, data, creada["id"])
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "cerrada"
    assert cuerpo["cerrada_por"] == str(
        data["actores"]["administrador"].id
    )
    assert cuerpo["cerrada_at"] is not None
    assert cuerpo["total_cobertura"] == creada["total_cobertura"]
    assert cuerpo["cantidad_practicas"] == creada["cantidad_practicas"]
    assert len(cuerpo["items"]) == len(creada["items"])


def test_cierre_repetido_es_idempotente(api_client, session_factory) -> None:
    """Edge: repeating the close changes nothing and audits once."""
    data = _setup(session_factory)
    creada = _crear(api_client, session_factory, data)
    primero = _cerrar(api_client, data, creada["id"])
    segundo = _cerrar(api_client, data, creada["id"])
    assert primero.status_code == 200, primero.text
    assert segundo.status_code == 200, segundo.text
    assert segundo.json()["cerrada_at"] == primero.json()["cerrada_at"]
    assert segundo.json()["total_cobertura"] == primero.json()["total_cobertura"]
    assert len(run(auditorias(session_factory, "liquidacion.cerrar"))) == 1


def test_editar_o_borrar_una_cerrada_devuelve_409(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    creada = _crear(api_client, session_factory, data)
    _cerrar(api_client, data, creada["id"])

    edicion = _editar(api_client, data, creada["id"])
    assert edicion.status_code == 409, edicion.text
    borrado = _borrar(api_client, data, creada["id"])
    assert borrado.status_code == 409, borrado.text

    liquidacion = run(
        leer_liquidacion(session_factory, uuid.UUID(creada["id"]))
    )
    assert liquidacion is not None
    assert liquidacion.estado == "cerrada"
    assert liquidacion.deleted_at is None
    assert liquidacion.observaciones is None


def test_borrado_de_borrador_libera_periodo_e_items(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    creada = _crear(api_client, session_factory, data)

    respuesta = _borrar(api_client, data, creada["id"])
    assert respuesta.status_code == 204, respuesta.text

    liquidacion = run(
        leer_liquidacion(session_factory, uuid.UUID(creada["id"]))
    )
    assert liquidacion is not None
    assert liquidacion.deleted_at is not None
    assert liquidacion.is_active is False
    assert all(
        item.deleted_at is not None
        for item in run(items_de(session_factory, liquidacion.id))
    )

    repeat = _borrar(api_client, data, creada["id"])
    assert repeat.status_code == 404, repeat.text

    nueva = post_liquidacion(api_client, data)
    assert nueva.status_code == 201, nueva.text
    assert nueva.json()["id"] != creada["id"]
    assert nueva.json()["items"][0]["item_presupuesto_id"] == (
        creada["items"][0]["item_presupuesto_id"]
    )
    assert run(contar_liquidaciones(session_factory)) == 2


def test_recepcion_no_cierra_pero_edita_observaciones(
    api_client, session_factory
) -> None:
    """Business rule: closing is admin-only; observations are reception's."""
    data = _setup(session_factory)
    creada = _crear(api_client, session_factory, data)

    cierre = _cerrar(
        api_client, data, creada["id"], actor="recepcionista"
    )
    assert cierre.status_code == 403, cierre.text

    edicion = _editar(
        api_client, data, creada["id"], actor="recepcionista"
    )
    assert edicion.status_code == 200, edicion.text
    assert edicion.json()["observaciones"] == "Observación de cierre"
    assert edicion.json()["estado"] == "borrador"

    borrado = _borrar(
        api_client, data, creada["id"], actor="recepcionista"
    )
    assert borrado.status_code == 403, borrado.text
