"""Budget creation endpoint: calculation, pending mode, RBAC and audit (C-12)."""

import uuid
from decimal import Decimal

from app.application.presupuestos import (
    CoberturaNoDisponible,
    get_cobertura_provider,
)
from app.infrastructure.uow import UnitOfWork
from app.main import app
from tests.integration.clinica_helpers import auditorias, otro_consultorio
from tests.integration.helpers import run
from tests.integration.presupuestos_helpers import setup_presupuestos
from tests.integration.recursos_helpers import (
    bearer,
    create_profesional,
)


def _setup(session_factory) -> dict[str, object]:
    return run(setup_presupuestos(session_factory))


def _items_cons_obt(prestaciones: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "prestacion_id": str(prestaciones["CONS"].id),
            "cantidad": 1,
        },
        {
            "prestacion_id": str(prestaciones["OBT"].id),
            "pieza": 16,
            "cantidad": 2,
        },
    ]


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


def _alta(
    api_client,
    actor,
    paciente_id: uuid.UUID,
    profesional_id: uuid.UUID,
    items: list[dict[str, object]],
    **headers: str,
):
    return api_client.post(
        "/presupuestos",
        json=_payload(paciente_id, profesional_id, items),
        headers={**bearer(actor), **headers},
    )


def _importe(valor: object) -> Decimal:
    return Decimal(str(valor))


def _una_prestacion(prestaciones, codigo: str, cantidad: int = 1, pieza=None):
    item: dict[str, object] = {
        "prestacion_id": str(prestaciones[codigo].id),
        "cantidad": cantidad,
    }
    if pieza is not None:
        item["pieza"] = pieza
    return [item]


# --- Expected path ----------------------------------------------------------


def test_alta_con_os_demo_devuelve_201_y_dos_items(api_client, session_factory) -> None:
    """Expected: price snapshot, per-item coverage and header totals."""
    data = _setup(session_factory)
    respuesta = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        _items_cons_obt(data["prestaciones"]),
    )

    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert body["estado"] == "borrador"
    assert body["cobertura_estado"] == "calculada"
    assert body["paciente_id"] == str(data["paciente_os_demo"].id)
    assert body["profesional_id"] == str(data["profesional"].id)
    assert body["creado_por"] == str(data["actores"]["administrador"].id)

    items = {item["prestacion_id"]: item for item in body["items"]}
    cons = items[str(data["prestaciones"]["CONS"].id)]
    obt = items[str(data["prestaciones"]["OBT"].id)]
    assert _importe(cons["precio_unitario"]) == Decimal("10000.00")
    assert _importe(cons["cobertura_item"]) == Decimal("6000.00")
    assert _importe(cons["copago_item"]) == Decimal("4000.00")
    assert _importe(obt["precio_unitario"]) == Decimal("25000.00")
    assert _importe(obt["cobertura_item"]) == Decimal("30000.00")
    assert _importe(obt["copago_item"]) == Decimal("20000.00")
    assert obt["pieza"] == 16 and obt["cantidad"] == 2

    assert _importe(body["subtotal"]) == Decimal("60000.00")
    assert _importe(body["cobertura_calculada"]) == Decimal("36000.00")
    assert _importe(body["copago"]) == Decimal("24000.00")


def test_alta_con_dos_items_de_cons_calcula_cobertura_12000(
    api_client, session_factory
) -> None:
    """Spec scenario: 2 × 10.000,00 al 60 % → cobertura 12.000,00."""
    data = _setup(session_factory)
    items = [
        {
            "prestacion_id": str(data["prestaciones"]["CONS"].id),
            "cantidad": 1,
        },
        {
            "prestacion_id": str(data["prestaciones"]["CONS"].id),
            "pieza": 16,
            "cantidad": 1,
        },
    ]
    respuesta = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        items,
    )
    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert _importe(body["subtotal"]) == Decimal("20000.00")
    assert _importe(body["cobertura_calculada"]) == Decimal("12000.00")
    assert _importe(body["copago"]) == Decimal("8000.00")


def test_alta_sin_obra_social_cobra_todo_al_paciente(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    respuesta = _alta(
        api_client,
        data["actores"]["odontologo"],
        data["paciente_propio"].id,
        data["profesional"].id,
        _una_prestacion(data["prestaciones"], "CONS", cantidad=2),
    )
    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert body["cobertura_estado"] == "calculada"
    assert _importe(body["subtotal"]) == Decimal("20000.00")
    assert _importe(body["cobertura_calculada"]) == Decimal("0.00")
    assert _importe(body["copago"]) == Decimal("20000.00")
    assert _importe(body["items"][0]["cobertura_item"]) == Decimal("0.00")


def test_prestacion_fuera_del_convenio_tiene_cobertura_cero_conocida(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    respuesta = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        _una_prestacion(data["prestaciones"], "EXO"),
    )
    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert body["cobertura_estado"] == "calculada"
    assert _importe(body["cobertura_calculada"]) == Decimal("0.00")
    assert _importe(body["copago"]) == Decimal("30000.00")
    assert _importe(body["items"][0]["cobertura_item"]) == Decimal("0.00")


# --- Validation and not-found boundaries ------------------------------------


def test_el_cliente_no_puede_fijar_precios_ni_totales(
    api_client, session_factory
) -> None:
    """Business error: amounts are server-owned; extra fields are 422."""
    data = _setup(session_factory)
    actor = data["actores"]["administrador"]
    item = _una_prestacion(data["prestaciones"], "CONS")[0]

    con_precio = _alta(
        api_client,
        actor,
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [{**item, "precio_unitario": "1.00"}],
    )
    assert con_precio.status_code == 422, con_precio.text

    con_total = _payload(
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [item],
    )
    con_total["subtotal"] = "1.00"
    respuesta = api_client.post(
        "/presupuestos", json=con_total, headers=bearer(actor)
    )
    assert respuesta.status_code == 422, respuesta.text

    assert run(auditorias(session_factory, "presupuesto.crear")) == []


def test_sin_items_o_items_vacios_responde_422(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    actor = data["actores"]["administrador"]
    base = {
        "paciente_id": str(data["paciente_os_demo"].id),
        "profesional_id": str(data["profesional"].id),
    }
    for body in ({**base}, {**base, "items": []}):
        respuesta = api_client.post(
            "/presupuestos", json=body, headers=bearer(actor)
        )
        assert respuesta.status_code == 422, respuesta.text
    assert run(auditorias(session_factory, "presupuesto.crear")) == []


def test_cantidad_no_positiva_responde_422(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    actor = data["actores"]["administrador"]
    for cantidad in (0, -1):
        respuesta = _alta(
            api_client,
            actor,
            data["paciente_os_demo"].id,
            data["profesional"].id,
            _una_prestacion(
                data["prestaciones"], "CONS", cantidad=cantidad
            ),
        )
        assert respuesta.status_code == 422, respuesta.text
    assert run(auditorias(session_factory, "presupuesto.crear")) == []


def test_pieza_fdi_invalida_responde_422_y_la_valida_se_acepta(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    actor = data["actores"]["administrador"]
    for pieza in (19, 49, 86):
        respuesta = _alta(
            api_client,
            actor,
            data["paciente_os_demo"].id,
            data["profesional"].id,
            _una_prestacion(
                data["prestaciones"], "CONS", pieza=pieza
            ),
        )
        assert respuesta.status_code == 422, (pieza, respuesta.text)

    valida = _alta(
        api_client,
        actor,
        data["paciente_os_demo"].id,
        data["profesional"].id,
        _una_prestacion(data["prestaciones"], "CONS", pieza=48),
    )
    assert valida.status_code == 201, valida.text
    assert valida.json()["items"][0]["pieza"] == 48


def test_referencias_inexistentes_o_de_otro_consultorio_404(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    actor = data["actores"]["administrador"]
    cons = _una_prestacion(data["prestaciones"], "CONS")

    inexistente_paciente = _alta(
        api_client, actor, uuid.uuid4(), data["profesional"].id, cons
    )
    assert inexistente_paciente.status_code == 404, inexistente_paciente.text

    inexistente_profesional = _alta(
        api_client,
        actor,
        data["paciente_os_demo"].id,
        uuid.uuid4(),
        cons,
    )
    assert (
        inexistente_profesional.status_code == 404
    ), inexistente_profesional.text

    inexistente_prestacion = _alta(
        api_client,
        actor,
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [{"prestacion_id": str(uuid.uuid4()), "cantidad": 1}],
    )
    assert (
        inexistente_prestacion.status_code == 404
    ), inexistente_prestacion.text

    ajeno = run(otro_consultorio(session_factory))
    paciente_ajeno = _alta(
        api_client,
        actor,
        ajeno["paciente_id"],
        data["profesional"].id,
        cons,
    )
    assert paciente_ajeno.status_code == 404, paciente_ajeno.text

    profesional_ajeno = run(
        create_profesional(
            session_factory, ajeno["consultorio_id"], "MP-AJENO-C12"
        )
    )
    profesional_de_otro = _alta(
        api_client,
        actor,
        data["paciente_os_demo"].id,
        profesional_ajeno.id,
        cons,
    )
    assert profesional_de_otro.status_code == 404, profesional_de_otro.text

    assert run(auditorias(session_factory, "presupuesto.crear")) == []


def test_paciente_o_prestacion_dados_de_baja_404(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    actor = data["actores"]["administrador"]
    cons = _una_prestacion(data["prestaciones"], "CONS")

    async def borrar_paciente() -> None:
        async with UnitOfWork(session_factory) as uow:
            paciente = await uow.pacientes.get(data["paciente_os_demo"].id)
            assert paciente is not None
            await uow.pacientes.soft_delete(paciente)

    async def borrar_prestacion() -> None:
        async with UnitOfWork(session_factory) as uow:
            prestacion = await uow.prestaciones.get(
                data["prestaciones"]["CONS"].id
            )
            assert prestacion is not None
            await uow.prestaciones.soft_delete(prestacion)

    run(borrar_paciente())
    assert (
        _alta(
            api_client,
            actor,
            data["paciente_os_demo"].id,
            data["profesional"].id,
            cons,
        ).status_code
        == 404
    )

    run(borrar_prestacion())
    assert (
        _alta(
            api_client,
            actor,
            data["paciente_propio"].id,
            data["profesional"].id,
            cons,
        ).status_code
        == 404
    )
    assert run(auditorias(session_factory, "presupuesto.crear")) == []


def test_profesional_inactivo_404(api_client, session_factory) -> None:
    data = _setup(session_factory)
    actor = data["actores"]["administrador"]

    async def borrar_profesional() -> None:
        async with UnitOfWork(session_factory) as uow:
            profesional = await uow.profesionales.get(
                data["profesional"].id
            )
            assert profesional is not None
            await uow.profesionales.soft_delete(profesional)

    run(borrar_profesional())
    respuesta = _alta(
        api_client,
        actor,
        data["paciente_os_demo"].id,
        data["profesional"].id,
        _una_prestacion(data["prestaciones"], "CONS"),
    )
    assert respuesta.status_code == 404, respuesta.text
    assert run(auditorias(session_factory, "presupuesto.crear")) == []


# --- Minimum RBAC for this slice -------------------------------------------


def test_administrador_y_odontologo_propio_crean(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    cons = _una_prestacion(data["prestaciones"], "CONS")

    del_admin = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional_ajeno"].id,
        cons,
    )
    assert del_admin.status_code == 201, del_admin.text

    del_odontologo = _alta(
        api_client,
        data["actores"]["odontologo"],
        data["paciente_propio"].id,
        data["profesional"].id,
        cons,
    )
    assert del_odontologo.status_code == 201, del_odontologo.text


def test_escrituras_ajenas_o_de_otros_roles_403(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    cons = _una_prestacion(data["prestaciones"], "CONS")

    casos = [
        # Dentist sending another professional.
        (
            data["actores"]["odontologo"],
            data["paciente_propio"].id,
            data["profesional_ajeno"].id,
        ),
        # Dentist over a patient linked only to another professional.
        (
            data["actores"]["odontologo"],
            data["paciente_ajeno"].id,
            data["profesional"].id,
        ),
        # Dentist without a `profesionales` row.
        (
            data["odontologo_sin_profesional"],
            data["paciente_propio"].id,
            data["profesional"].id,
        ),
        # Dentist over a patient without a live turn.
        (
            data["actores"]["odontologo"],
            data["paciente_sin_turno"].id,
            data["profesional"].id,
        ),
    ]
    for actor, paciente_id, profesional_id in casos:
        respuesta = _alta(
            api_client, actor, paciente_id, profesional_id, cons
        )
        assert respuesta.status_code == 403, respuesta.text

    for rol in ("recepcionista", "asistente", "auditor"):
        respuesta = _alta(
            api_client,
            data["actores"][rol],
            data["paciente_os_demo"].id,
            data["profesional"].id,
            cons,
        )
        assert respuesta.status_code == 403, (rol, respuesta.text)

    anonimo = api_client.post(
        "/presupuestos",
        json=_payload(
            data["paciente_os_demo"].id, data["profesional"].id, cons
        ),
    )
    assert anonimo.status_code == 401, anonimo.text
    assert run(auditorias(session_factory, "presupuesto.crear")) == []


# --- Audit ------------------------------------------------------------------


def test_alta_audita_usuario_ip_y_dispositivo(api_client, session_factory) -> None:
    data = _setup(session_factory)
    respuesta = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        _una_prestacion(data["prestaciones"], "CONS"),
        **{"User-Agent": "pytest-agent"},
    )
    assert respuesta.status_code == 201, respuesta.text

    registros = run(auditorias(session_factory, "presupuesto.crear"))
    assert len(registros) == 1
    registro = registros[0]
    assert registro.entidad == "presupuesto"
    assert registro.entidad_id == respuesta.json()["id"]
    assert registro.usuario_id == data["actores"]["administrador"].id
    assert registro.ip == "testclient"
    assert registro.dispositivo == "pytest-agent"

    # A rejected create leaves no extra audit row.
    rechazado = _alta(
        api_client,
        data["actores"]["administrador"],
        uuid.uuid4(),
        data["profesional"].id,
        _una_prestacion(data["prestaciones"], "CONS"),
    )
    assert rechazado.status_code == 404
    assert len(run(auditorias(session_factory, "presupuesto.crear"))) == 1


# --- Pending coverage -------------------------------------------------------


class _ProveedorCaido:
    async def resolver(self, uow, paciente):
        raise CoberturaNoDisponible("nomenclador caído")


def test_convenio_sin_porcentaje_queda_pendiente(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    respuesta = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_sin_porcentaje"].id,
        data["profesional"].id,
        _una_prestacion(data["prestaciones"], "CONS"),
    )
    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert body["cobertura_estado"] == "pendiente_verificacion"
    assert _importe(body["cobertura_calculada"]) == Decimal("0.00")
    assert _importe(body["copago"]) == Decimal("10000.00")


def test_convenio_inactivo_queda_pendiente(api_client, session_factory) -> None:
    data = _setup(session_factory)
    respuesta = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_convenio_inactivo"].id,
        data["profesional"].id,
        _una_prestacion(data["prestaciones"], "CONS"),
    )
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["cobertura_estado"] == "pendiente_verificacion"
    assert _importe(respuesta.json()["cobertura_calculada"]) == Decimal(
        "0.00"
    )


def test_proveedor_no_disponible_responde_201_y_persiste(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    app.dependency_overrides[get_cobertura_provider] = (
        lambda: _ProveedorCaido()
    )
    try:
        respuesta = _alta(
            api_client,
            data["actores"]["administrador"],
            data["paciente_os_demo"].id,
            data["profesional"].id,
            _una_prestacion(data["prestaciones"], "CONS"),
        )
    finally:
        app.dependency_overrides.pop(get_cobertura_provider, None)

    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert body["cobertura_estado"] == "pendiente_verificacion"
    assert _importe(body["cobertura_calculada"]) == Decimal("0.00")
    assert _importe(body["copago"]) == Decimal("10000.00")

    async def contar() -> tuple[int, int]:
        async with session_factory() as session:
            from sqlalchemy import text

            presupuestos = await session.scalar(
                text("SELECT count(*) FROM presupuestos")
            )
            items = await session.scalar(
                text("SELECT count(*) FROM items_presupuesto")
            )
        return int(presupuestos or 0), int(items or 0)

    assert run(contar()) == (1, 1)


# --- SQL assertions on persisted totals ------------------------------------


def test_sql_de_totales_coherentes_y_pendiente_distinto_de_cero(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    calculado = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_os_demo"].id,
        data["profesional"].id,
        [
            {
                "prestacion_id": str(data["prestaciones"]["CONS"].id),
                "cantidad": 2,
            },
            {
                "prestacion_id": str(data["prestaciones"]["OBT"].id),
                "pieza": 16,
                "cantidad": 2,
            },
        ],
    )
    assert calculado.status_code == 201, calculado.text
    presupuesto_id = calculado.json()["id"]

    pendiente = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_sin_porcentaje"].id,
        data["profesional"].id,
        _una_prestacion(data["prestaciones"], "CONS"),
    )
    assert pendiente.status_code == 201, pendiente.text

    cero_conocido = _alta(
        api_client,
        data["actores"]["administrador"],
        data["paciente_propio"].id,
        data["profesional"].id,
        _una_prestacion(data["prestaciones"], "CONS"),
    )
    assert cero_conocido.status_code == 201, cero_conocido.text

    async def verificar() -> None:
        from sqlalchemy import text

        async with session_factory() as session:
            fila = (
                await session.execute(
                    text(
                        "SELECT p.subtotal, p.cobertura_calculada, p.copago, "
                        "COALESCE(SUM(i.precio_unitario * i.cantidad), 0) "
                        "AS total_items, "
                        "COALESCE(SUM(i.cobertura_item), 0) AS cobertura_items, "
                        "COALESCE(SUM(i.copago_item), 0) AS copago_items "
                        "FROM presupuestos p "
                        "LEFT JOIN items_presupuesto i "
                        "ON i.presupuesto_id = p.id "
                        "AND i.deleted_at IS NULL "
                        "WHERE p.id = :id GROUP BY p.id"
                    ),
                    {"id": presupuesto_id},
                )
            ).one()
            subtotal, cobertura, copago, total_items, cov_items, cop_items = fila
            assert subtotal == total_items
            assert cobertura == cov_items
            assert copago == cop_items
            assert subtotal == cobertura + copago

            estados = (
                await session.execute(
                    text(
                        "SELECT id, cobertura_estado, cobertura_calculada "
                        "FROM presupuestos WHERE id IN (:pendiente, :cero)"
                    ),
                    {
                        "pendiente": pendiente.json()["id"],
                        "cero": cero_conocido.json()["id"],
                    },
                )
            ).all()
        por_id = {str(fila[0]): fila for fila in estados}
        assert (
            por_id[pendiente.json()["id"]][1] == "pendiente_verificacion"
        )
        assert por_id[cero_conocido.json()["id"]][1] == "calculada"
        assert por_id[pendiente.json()["id"]][2] == 0
        assert por_id[cero_conocido.json()["id"]][2] == 0

    run(verificar())
