"""Budget state machine and soft delete (C-12 group 6)."""

import uuid
from decimal import Decimal

from tests.integration.clinica_helpers import auditorias
from tests.integration.helpers import run
from tests.integration.presupuestos_helpers import setup_presupuestos
from tests.integration.recursos_helpers import bearer


def _setup(session_factory) -> dict[str, object]:
    return run(setup_presupuestos(session_factory))


def _item(prestaciones, codigo: str = "CONS", cantidad: int = 1):
    return {
        "prestacion_id": str(prestaciones[codigo].id),
        "cantidad": cantidad,
    }


def _alta(api_client, data, actor=None, codigo: str = "CONS"):
    return api_client.post(
        "/presupuestos",
        json={
            "paciente_id": str(data["paciente_os_demo"].id),
            "profesional_id": str(data["profesional"].id),
            "items": [_item(data["prestaciones"], codigo)],
        },
        headers=bearer(actor or data["actores"]["administrador"]),
    )


def _estado(api_client, data, presupuesto_id, estado: str, actor=None):
    return api_client.patch(
        f"/presupuestos/{presupuesto_id}/estado",
        json={"estado": estado},
        headers=bearer(actor or data["actores"]["administrador"]),
    )


def _importe(valor: object) -> Decimal:
    return Decimal(str(valor))


def test_camino_completo_de_estados(api_client, session_factory) -> None:
    data = _setup(session_factory)
    creado = _alta(api_client, data)
    assert creado.status_code == 201, creado.text
    presupuesto_id = creado.json()["id"]

    aceptado = _estado(api_client, data, presupuesto_id, "aceptado")
    assert aceptado.status_code == 200, aceptado.text
    assert aceptado.json()["estado"] == "aceptado"

    en_curso = _estado(api_client, data, presupuesto_id, "en_curso")
    assert en_curso.status_code == 200, en_curso.text
    assert en_curso.json()["estado"] == "en_curso"

    finalizado = _estado(api_client, data, presupuesto_id, "finalizado")
    assert finalizado.status_code == 200, finalizado.text
    assert finalizado.json()["estado"] == "finalizado"

    acciones = {
        registro.accion
        for registro in run(
            auditorias(session_factory)
        )
        if registro.accion.startswith("presupuesto.")
    }
    assert {
        "presupuesto.crear",
        "presupuesto.aceptar",
        "presupuesto.en_curso",
        "presupuesto.finalizar",
    } <= acciones


def test_saltos_invalidos_desde_borrador_422(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    creado = _alta(api_client, data)
    presupuesto_id = creado.json()["id"]

    for destino in ("en_curso", "finalizado"):
        respuesta = _estado(api_client, data, presupuesto_id, destino)
        assert respuesta.status_code == 422, (destino, respuesta.text)

    ficha = api_client.get(
        f"/presupuestos/{presupuesto_id}",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert ficha.json()["estado"] == "borrador"


def test_aceptado_no_se_rechaza_422(api_client, session_factory) -> None:
    data = _setup(session_factory)
    creado = _alta(api_client, data)
    presupuesto_id = creado.json()["id"]
    assert _estado(api_client, data, presupuesto_id, "aceptado").status_code == 200

    respuesta = _estado(api_client, data, presupuesto_id, "rechazado")
    assert respuesta.status_code == 422, respuesta.text

    ficha = api_client.get(
        f"/presupuestos/{presupuesto_id}",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert ficha.json()["estado"] == "aceptado"


def test_estados_terminales_422(api_client, session_factory) -> None:
    data = _setup(session_factory)
    rechazado = _alta(api_client, data).json()["id"]
    assert _estado(api_client, data, rechazado, "rechazado").status_code == 200
    assert (
        _estado(api_client, data, rechazado, "aceptado").status_code == 422
    )

    finalizado = _alta(api_client, data).json()["id"]
    for destino in ("aceptado", "en_curso", "finalizado"):
        assert (
            _estado(api_client, data, finalizado, destino).status_code == 200
        )
    assert (
        _estado(api_client, data, finalizado, "en_curso").status_code == 422
    )


def test_repetir_estado_actual_200_sin_auditoria_extra(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    creado = _alta(api_client, data)
    presupuesto_id = creado.json()["id"]

    primera = _estado(api_client, data, presupuesto_id, "aceptado")
    assert primera.status_code == 200, primera.text
    antes = len(run(auditorias(session_factory, "presupuesto.aceptar")))

    repetida = _estado(api_client, data, presupuesto_id, "aceptado")
    assert repetida.status_code == 200, repetida.text
    assert repetida.json()["estado"] == "aceptado"
    despues = len(run(auditorias(session_factory, "presupuesto.aceptar")))
    assert despues == antes


def test_borrador_a_borrador_es_idempotente(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    creado = _alta(api_client, data)
    respuesta = _estado(api_client, data, creado.json()["id"], "borrador")
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "borrador"
    assert run(auditorias(session_factory, "presupuesto.aceptar")) == []


def test_destino_inexistente_o_borrador_desde_otro_estado_422(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    creado = _alta(api_client, data)
    presupuesto_id = creado.json()["id"]

    inexistente = _estado(api_client, data, presupuesto_id, "inexistente")
    assert inexistente.status_code == 422, inexistente.text

    assert _estado(api_client, data, presupuesto_id, "aceptado").status_code == 200
    volver = _estado(api_client, data, presupuesto_id, "borrador")
    assert volver.status_code == 422, volver.text


def test_patch_con_campos_clinicos_422(api_client, session_factory) -> None:
    data = _setup(session_factory)
    creado = _alta(api_client, data)
    respuesta = api_client.patch(
        f"/presupuestos/{creado.json()['id']}/estado",
        json={
            "estado": "aceptado",
            "consentimiento": "firmado",
            "texto_version": "v1",
            "firma_ref": "sha256:" + "a" * 64,
        },
        headers=bearer(data["actores"]["administrador"]),
    )
    assert respuesta.status_code == 422, respuesta.text

    ficha = api_client.get(
        f"/presupuestos/{creado.json()['id']}",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert ficha.json()["estado"] == "borrador"


def test_aceptacion_no_exige_consentimiento_ni_historia(
    api_client, session_factory
) -> None:
    """D8: accepting a plan is not gated by a consent or a clinical file."""
    data = _setup(session_factory)
    creado = _alta(api_client, data, codigo="EXO")
    assert creado.status_code == 201, creado.text

    aceptado = _estado(api_client, data, creado.json()["id"], "aceptado")
    assert aceptado.status_code == 200, aceptado.text
    assert aceptado.json()["estado"] == "aceptado"

    async def contar() -> tuple[int, int]:
        from sqlalchemy import text

        async with session_factory() as session:
            consentimientos = await session.scalar(
                text("SELECT count(*) FROM consentimientos")
            )
            historias = await session.scalar(
                text("SELECT count(*) FROM historias_clinicas")
            )
        return int(consentimientos or 0), int(historias or 0)

    assert run(contar()) == (0, 0)
    assert _importe(aceptado.json()["copago"]) == Decimal("30000.00")


# --- 6.3 Soft delete --------------------------------------------------------


def test_delete_borrador_204_y_desaparece_del_listado(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    creado = _alta(api_client, data)
    presupuesto_id = creado.json()["id"]

    borrado = api_client.delete(
        f"/presupuestos/{presupuesto_id}", headers=headers
    )
    assert borrado.status_code == 204, borrado.text

    listado = api_client.get("/presupuestos", headers=headers)
    assert str(presupuesto_id) not in {
        presupuesto["id"] for presupuesto in listado.json()
    }
    assert (
        api_client.get(
            f"/presupuestos/{presupuesto_id}", headers=headers
        ).status_code
        == 404
    )


def test_delete_aceptado_409_y_no_borra(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    creado = _alta(api_client, data)
    presupuesto_id = creado.json()["id"]
    assert _estado(api_client, data, presupuesto_id, "aceptado").status_code == 200

    borrado = api_client.delete(
        f"/presupuestos/{presupuesto_id}", headers=headers
    )
    assert borrado.status_code == 409, borrado.text

    ficha = api_client.get(
        f"/presupuestos/{presupuesto_id}", headers=headers
    )
    assert ficha.status_code == 200
    assert ficha.json()["estado"] == "aceptado"


def test_delete_inexistente_404(api_client, session_factory) -> None:
    data = _setup(session_factory)
    respuesta = api_client.delete(
        f"/presupuestos/{uuid.uuid4()}",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert respuesta.status_code == 404, respuesta.text
