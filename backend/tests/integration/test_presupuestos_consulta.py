"""Budgets: read, edit, recalculate and price snapshot (C-12 group 5)."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text

from app.infrastructure.uow import UnitOfWork
from tests.integration.clinica_helpers import otro_consultorio
from tests.integration.helpers import run
from tests.integration.presupuestos_helpers import (
    actualizar_reglas_cobertura,
    cambiar_precio_prestacion,
    insertar_item_db,
    insertar_presupuesto_db,
    setup_presupuestos,
)
from tests.integration.recursos_helpers import bearer, create_profesional


def _setup(session_factory) -> dict[str, object]:
    return run(setup_presupuestos(session_factory))


def _item(prestaciones, codigo: str, cantidad: int = 1, pieza=None):
    item: dict[str, object] = {
        "prestacion_id": str(prestaciones[codigo].id),
        "cantidad": cantidad,
    }
    if pieza is not None:
        item["pieza"] = pieza
    return item


def _payload(
    paciente_id: uuid.UUID,
    profesional_id: uuid.UUID,
    items: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "paciente_id": str(paciente_id),
        "profesional_id": str(profesional_id),
        "items": items,
    }


def _alta(api_client, actor, paciente_id, profesional_id, items, **headers):
    return api_client.post(
        "/presupuestos",
        json=_payload(paciente_id, profesional_id, items),
        headers={**bearer(actor), **headers},
    )


def _importe(valor: object) -> Decimal:
    return Decimal(str(valor))


def _fijar_estado(session_factory, presupuesto_id, estado: str) -> None:
    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "UPDATE presupuestos SET estado = :estado WHERE id = :id"
                ),
                {"estado": estado, "id": presupuesto_id},
            )

    run(scenario())


def _crear_db(
    session_factory,
    data,
    *,
    paciente_id=None,
    profesional_id=None,
    estado: str = "borrador",
    creado_en: datetime | None = None,
) -> uuid.UUID:
    return run(
        insertar_presupuesto_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=paciente_id or data["paciente_os_demo"].id,
            profesional_id=profesional_id or data["profesional"].id,
            creado_por=data["actores"]["odontologo"].id,
            estado=estado,
            creado_en=creado_en,
        )
    )


# --- 5.1 Read ---------------------------------------------------------------


def test_ficha_devuelve_items_y_totales(api_client, session_factory) -> None:
    data = _setup(session_factory)
    creado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [
            _item(data["prestaciones"], "CONS", 2),
            _item(data["prestaciones"], "OBT", 2, pieza=16),
        ],
    )
    assert creado.status_code == 201, creado.text
    presupuesto_id = creado.json()["id"]

    ficha = api_client.get(
        f"/presupuestos/{presupuesto_id}",
        headers=bearer(data["actores"]["recepcionista"]),
    )
    assert ficha.status_code == 200, ficha.text
    body = ficha.json()
    assert body["id"] == presupuesto_id
    assert body["estado"] == "borrador"
    assert body["cobertura_estado"] == "calculada"
    assert len(body["items"]) == 2
    assert _importe(body["subtotal"]) == Decimal("70000.00")
    assert _importe(body["cobertura_calculada"]) == Decimal("42000.00")
    assert _importe(body["copago"]) == Decimal("28000.00")
    assert {
        _importe(item["precio_unitario"]) for item in body["items"]
    } == {Decimal("10000.00"), Decimal("25000.00")}


def test_listado_filtra_y_ordena_descendente(api_client, session_factory) -> None:
    data = _setup(session_factory)
    base = datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc)
    viejo = _crear_db(session_factory, data, creado_en=base)
    nuevo = _crear_db(
        session_factory,
        data,
        estado="aceptado",
        creado_en=base + timedelta(days=1),
    )
    ajeno = _crear_db(
        session_factory,
        data,
        paciente_id=data["paciente_ajeno"].id,
        profesional_id=data["profesional_ajeno"].id,
        creado_en=base + timedelta(days=2),
    )
    headers = bearer(data["actores"]["administrador"])

    por_paciente = api_client.get(
        f"/presupuestos?paciente_id={data['paciente_os_demo'].id}",
        headers=headers,
    )
    assert por_paciente.status_code == 200, por_paciente.text
    assert [p["id"] for p in por_paciente.json()] == [
        str(nuevo),
        str(viejo),
    ]

    por_profesional = api_client.get(
        f"/presupuestos?profesional_id={data['profesional_ajeno'].id}",
        headers=headers,
    )
    assert por_profesional.status_code == 200, por_profesional.text
    assert [p["id"] for p in por_profesional.json()] == [str(ajeno)]

    por_estado = api_client.get(
        "/presupuestos?estado=borrador", headers=headers
    )
    assert por_estado.status_code == 200, por_estado.text
    assert [p["id"] for p in por_estado.json()] == [str(ajeno), str(viejo)]

    todos = api_client.get("/presupuestos", headers=headers)
    assert todos.status_code == 200, todos.text
    assert [p["id"] for p in todos.json()] == [
        str(ajeno),
        str(nuevo),
        str(viejo),
    ]


def test_consulta_rechaza_query_desconocida(api_client, session_factory) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    presupuesto_id = _crear_db(session_factory, data)

    assert (
        api_client.get("/presupuestos?foo=1", headers=headers).status_code
        == 422
    )
    assert (
        api_client.get(
            f"/presupuestos/{presupuesto_id}?foo=1", headers=headers
        ).status_code
        == 422
    )


def test_ficha_inexistente_o_de_otro_consultorio_404(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])

    assert (
        api_client.get(
            f"/presupuestos/{uuid.uuid4()}", headers=headers
        ).status_code
        == 404
    )

    ajeno = run(otro_consultorio(session_factory))
    profesional_ajeno = run(
        create_profesional(
            session_factory, ajeno["consultorio_id"], "MP-OTRO-C12"
        )
    )
    presupuesto_ajeno = run(
        insertar_presupuesto_db(
            session_factory,
            consultorio_id=ajeno["consultorio_id"],
            paciente_id=ajeno["paciente_id"],
            profesional_id=profesional_ajeno.id,
            creado_por=data["actores"]["administrador"].id,
        )
    )
    assert (
        api_client.get(
            f"/presupuestos/{presupuesto_ajeno}", headers=headers
        ).status_code
        == 404
    )


def test_odontologo_lista_solo_los_propios(api_client, session_factory) -> None:
    data = _setup(session_factory)
    propio = _crear_db(session_factory, data)
    _crear_db(
        session_factory,
        data,
        paciente_id=data["paciente_ajeno"].id,
        profesional_id=data["profesional_ajeno"].id,
    )

    respuesta = api_client.get(
        "/presupuestos", headers=bearer(data["actores"]["odontologo"])
    )
    assert respuesta.status_code == 200, respuesta.text
    assert [p["id"] for p in respuesta.json()] == [str(propio)]


# --- 5.3 / 5.4 Edit ---------------------------------------------------------


def test_put_reemplaza_items_y_recalcula(api_client, session_factory) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    creado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [_item(data["prestaciones"], "CONS")],
    )
    assert creado.status_code == 201, creado.text
    presupuesto_id = creado.json()["id"]

    editado = api_client.put(
        f"/presupuestos/{presupuesto_id}",
        json=_payload(
            data["paciente_os_demo"].id,
            data["profesional"].id,
            [
                _item(data["prestaciones"], "CONS", 2),
                _item(data["prestaciones"], "OBT", 1, pieza=16),
            ],
        ),
        headers=headers,
    )
    assert editado.status_code == 200, editado.text
    body = editado.json()
    assert len(body["items"]) == 2
    assert _importe(body["subtotal"]) == Decimal("45000.00")
    assert _importe(body["cobertura_calculada"]) == Decimal("27000.00")
    assert _importe(body["copago"]) == Decimal("18000.00")

    # Replaced lines are soft-deleted, never physically removed.
    async def items_activos() -> list[uuid.UUID]:
        async with session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT id FROM items_presupuesto "
                    "WHERE presupuesto_id = :id AND deleted_at IS NULL"
                ),
                {"id": presupuesto_id},
            )
            return [fila[0] for fila in result.all()]

    activos = run(items_activos())
    assert len(activos) == 2
    assert len(creado.json()["items"]) == 1
    assert creado.json()["items"][0]["id"] not in {
        str(item_id) for item_id in activos
    }


def test_put_fuera_de_borrador_409_sin_cambios(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    creado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [_item(data["prestaciones"], "CONS")],
    )
    presupuesto_id = creado.json()["id"]
    _fijar_estado(session_factory, presupuesto_id, "aceptado")

    intento = api_client.put(
        f"/presupuestos/{presupuesto_id}",
        json=_payload(
            data["paciente_os_demo"].id,
            data["profesional"].id,
            [_item(data["prestaciones"], "OBT", 3, pieza=16)],
        ),
        headers=headers,
    )
    assert intento.status_code == 409, intento.text

    ficha = api_client.get(
        f"/presupuestos/{presupuesto_id}", headers=headers
    )
    assert ficha.json()["estado"] == "aceptado"
    assert len(ficha.json()["items"]) == 1
    assert _importe(ficha.json()["subtotal"]) == Decimal("10000.00")


def test_put_con_importes_del_cliente_422(api_client, session_factory) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    creado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [_item(data["prestaciones"], "CONS")],
    )
    presupuesto_id = creado.json()["id"]

    item = _item(data["prestaciones"], "CONS")
    con_precio = _payload(
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [{**item, "precio_unitario": "1.00"}],
    )
    assert (
        api_client.put(
            f"/presupuestos/{presupuesto_id}",
            json=con_precio,
            headers=headers,
        ).status_code
        == 422
    )

    con_total = _payload(
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [item],
    )
    con_total["subtotal"] = "1.00"
    assert (
        api_client.put(
            f"/presupuestos/{presupuesto_id}",
            json=con_total,
            headers=headers,
        ).status_code
        == 422
    )

    ficha = api_client.get(
        f"/presupuestos/{presupuesto_id}", headers=headers
    )
    assert len(ficha.json()["items"]) == 1


def test_put_cambia_paciente_y_recalcula_cobertura(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    creado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_propio"].id,
        data["profesional"].id,
        [_item(data["prestaciones"], "CONS")],
    )
    assert creado.status_code == 201, creado.text
    assert _importe(creado.json()["cobertura_calculada"]) == Decimal("0.00")

    editado = api_client.put(
        f"/presupuestos/{creado.json()['id']}",
        json=_payload(
            data["paciente_os_demo"].id,
            data["profesional"].id,
            [_item(data["prestaciones"], "CONS")],
        ),
        headers=headers,
    )
    assert editado.status_code == 200, editado.text
    body = editado.json()
    assert body["paciente_id"] == str(data["paciente_os_demo"].id)
    assert _importe(body["cobertura_calculada"]) == Decimal("6000.00")
    assert _importe(body["copago"]) == Decimal("4000.00")


def test_put_resnapshot_del_precio_vigente(api_client, session_factory) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    creado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [_item(data["prestaciones"], "CONS")],
    )
    presupuesto_id = creado.json()["id"]
    run(
        cambiar_precio_prestacion(
            session_factory,
            data["prestaciones"]["CONS"].id,
            Decimal("12000.00"),
        )
    )

    editado = api_client.put(
        f"/presupuestos/{presupuesto_id}",
        json=_payload(
            data["paciente_os_demo"].id,
            data["profesional"].id,
            [_item(data["prestaciones"], "CONS", 2)],
        ),
        headers=headers,
    )
    assert editado.status_code == 200, editado.text
    assert _importe(editado.json()["items"][0]["precio_unitario"]) == Decimal(
        "12000.00"
    )
    assert _importe(editado.json()["subtotal"]) == Decimal("24000.00")
    assert _importe(editado.json()["cobertura_calculada"]) == Decimal(
        "14400.00"
    )


# --- 5.5 / 5.6 Recalculate --------------------------------------------------


def test_recalcular_pendiente_a_calculada_sin_tocar_precios(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    creado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_sin_porcentaje"].id,
        data["profesional"].id,
        [_item(data["prestaciones"], "CONS", 2)],
    )
    assert creado.status_code == 201, creado.text
    assert creado.json()["cobertura_estado"] == "pendiente_verificacion"
    precio_original = _importe(
        creado.json()["items"][0]["precio_unitario"]
    )

    run(
        actualizar_reglas_cobertura(
            session_factory,
            data["obra_social_sin_porcentaje_id"],
            {
                "cobertura_porcentaje": 60,
                "prestaciones_cubiertas": ["CONS"],
            },
        )
    )

    recalculado = api_client.post(
        f"/presupuestos/{creado.json()['id']}/recalcular",
        json={},
        headers=headers,
    )
    assert recalculado.status_code == 200, recalculado.text
    body = recalculado.json()
    assert body["cobertura_estado"] == "calculada"
    assert _importe(body["items"][0]["precio_unitario"]) == precio_original
    assert _importe(body["items"][0]["cobertura_item"]) == Decimal(
        "12000.00"
    )
    assert _importe(body["cobertura_calculada"]) == Decimal("12000.00")
    assert _importe(body["subtotal"]) == Decimal("20000.00")


def test_recalcular_fuera_de_borrador_409(api_client, session_factory) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    creado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [_item(data["prestaciones"], "CONS")],
    )
    presupuesto_id = creado.json()["id"]
    _fijar_estado(session_factory, presupuesto_id, "aceptado")

    respuesta = api_client.post(
        f"/presupuestos/{presupuesto_id}/recalcular",
        json={},
        headers=headers,
    )
    assert respuesta.status_code == 409, respuesta.text
    ficha = api_client.get(
        f"/presupuestos/{presupuesto_id}", headers=headers
    )
    assert _importe(ficha.json()["cobertura_calculada"]) == Decimal("6000.00")


def test_recalcular_con_campos_extra_422(api_client, session_factory) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    creado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [_item(data["prestaciones"], "CONS")],
    )
    respuesta = api_client.post(
        f"/presupuestos/{creado.json()['id']}/recalcular",
        json={"cobertura_item": "1.00"},
        headers=headers,
    )
    assert respuesta.status_code == 422, respuesta.text


# --- 5.7 Snapshot -----------------------------------------------------------


def test_cambio_de_precio_no_altera_presupuesto_existente(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    creado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [_item(data["prestaciones"], "CONS", 2)],
    )
    run(
        cambiar_precio_prestacion(
            session_factory,
            data["prestaciones"]["CONS"].id,
            Decimal("99999.00"),
        )
    )

    ficha = api_client.get(
        f"/presupuestos/{creado.json()['id']}", headers=headers
    )
    assert ficha.status_code == 200, ficha.text
    assert _importe(ficha.json()["items"][0]["precio_unitario"]) == Decimal(
        "10000.00"
    )
    assert _importe(ficha.json()["subtotal"]) == Decimal("20000.00")
    assert _importe(ficha.json()["cobertura_calculada"]) == Decimal(
        "12000.00"
    )


def test_cambio_de_precio_no_altera_un_aceptado(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    creado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [_item(data["prestaciones"], "OBT", 1, pieza=16)],
    )
    presupuesto_id = creado.json()["id"]
    _fijar_estado(session_factory, presupuesto_id, "aceptado")
    run(
        cambiar_precio_prestacion(
            session_factory,
            data["prestaciones"]["OBT"].id,
            Decimal("50000.00"),
        )
    )

    ficha = api_client.get(
        f"/presupuestos/{presupuesto_id}", headers=headers
    )
    assert ficha.status_code == 200, ficha.text
    assert ficha.json()["estado"] == "aceptado"
    assert _importe(ficha.json()["items"][0]["precio_unitario"]) == Decimal(
        "25000.00"
    )
    assert _importe(ficha.json()["cobertura_calculada"]) == Decimal(
        "15000.00"
    )


def test_baja_de_prestacion_no_rompe_ficha_y_bloquea_altas(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    creado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [_item(data["prestaciones"], "CONS")],
    )
    presupuesto_id = creado.json()["id"]
    _fijar_estado(session_factory, presupuesto_id, "aceptado")

    async def borrar_prestacion() -> None:
        async with UnitOfWork(session_factory) as uow:
            prestacion = await uow.prestaciones.get(
                data["prestaciones"]["CONS"].id
            )
            assert prestacion is not None
            await uow.prestaciones.soft_delete(prestacion)

    run(borrar_prestacion())

    ficha = api_client.get(
        f"/presupuestos/{presupuesto_id}", headers=headers
    )
    assert ficha.status_code == 200, ficha.text
    assert _importe(ficha.json()["items"][0]["precio_unitario"]) == Decimal(
        "10000.00"
    )

    nuevo = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [_item(data["prestaciones"], "CONS")],
    )
    assert nuevo.status_code == 404, nuevo.text


def test_put_recotiza_dos_items_de_la_misma_prestacion(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    headers = bearer(data["actores"]["administrador"])
    creado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [_item(data["prestaciones"], "CONS")],
    )
    run(
        cambiar_precio_prestacion(
            session_factory,
            data["prestaciones"]["CONS"].id,
            Decimal("12000.00"),
        )
    )

    editado = api_client.put(
        f"/presupuestos/{creado.json()['id']}",
        json=_payload(
            data["paciente_os_demo"].id,
            data["profesional"].id,
            [
                _item(data["prestaciones"], "CONS"),
                _item(data["prestaciones"], "CONS", pieza=16),
            ],
        ),
        headers=headers,
    )
    assert editado.status_code == 200, editado.text
    body = editado.json()
    assert [_importe(item["precio_unitario"]) for item in body["items"]] == [
        Decimal("12000.00"),
        Decimal("12000.00"),
    ]
    assert _importe(body["subtotal"]) == Decimal("24000.00")
    assert _importe(body["cobertura_calculada"]) == Decimal("14400.00")
