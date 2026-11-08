"""C-13 refunds and payment queries (group 11)."""

import uuid

from app.infrastructure.mercadopago import TestMercadoPagoClient
from tests.integration.caja_helpers import insertar_cobro_db
from tests.integration.clinica_helpers import auditorias, otro_consultorio
from tests.integration.cobros_helpers import (
    cobro_payload,
    leer_cobro,
    movimientos_de,
    mp_override,
    setup_cobros,
)
from tests.integration.helpers import run
from tests.integration.recursos_helpers import bearer

_UA = "pytest-ua-c13-refund"


class FailingMercadoPago:
    async def crear_preferencia(self, **kwargs):
        raise RuntimeError("no debe llamarse al proveedor")

    async def consultar_pago(self, pago_id):
        return None


def _setup(session_factory) -> dict[str, object]:
    return run(setup_cobros(session_factory))


def _crear(api_client, data, **overrides):
    respuesta = api_client.post(
        "/cobros",
        json=cobro_payload(data, **overrides),
        headers={**bearer(data["actores"]["administrador"]), "User-Agent": _UA},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _crear_mp_pendiente(api_client, data) -> dict[str, object]:
    cliente = TestMercadoPagoClient()
    with mp_override(cliente):
        respuesta = api_client.post(
            "/cobros",
            json=cobro_payload(
                data,
                tipo="sena",
                medio="mercadopago",
                monto="10000.00",
                turno_id=data["turnos_cobro"]["sena"],
            ),
            headers=bearer(data["actores"]["administrador"]),
        )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _reembolsar(api_client, data, cobro_id, *, actor="administrador"):
    return api_client.post(
        f"/cobros/{cobro_id}/reembolsar",
        headers={
            **bearer(data["actores"][actor]),
            "User-Agent": _UA,
        },
    )


def test_reembolso_aprobado_200_con_auditoria(
    api_client, session_factory
) -> None:
    """Expected: approved cash becomes refunded and leaves one audit row."""
    data = _setup(session_factory)
    cobro = _crear(api_client, data)
    respuesta = _reembolsar(api_client, data, cobro["id"])
    assert respuesta.status_code == 200, respuesta.text
    body = respuesta.json()
    assert body["estado"] == "reembolsado"
    assert body["monto"] == "15000.00"

    filas = [
        fila
        for fila in run(auditorias(session_factory))
        if fila.accion == "cobro.reembolsar"
    ]
    assert len(filas) == 1
    assert filas[0].entidad == "cobro"
    assert filas[0].entidad_id == cobro["id"]
    assert filas[0].usuario_id == data["actores"]["administrador"].id
    assert filas[0].ip == "testclient"
    assert filas[0].dispositivo == _UA


def test_reembolso_repetido_es_idempotente(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    cobro = _crear(api_client, data)
    assert _reembolsar(api_client, data, cobro["id"]).status_code == 200
    repetido = _reembolsar(api_client, data, cobro["id"])
    assert repetido.status_code == 200, repetido.text
    filas = run(auditorias(session_factory, "cobro.reembolsar"))
    assert len(filas) == 1


def test_reembolso_no_aprobado_409(api_client, session_factory) -> None:
    """Business error: pending, rejected and lost payments cannot be refunded."""
    data = _setup(session_factory)
    pendiente = _crear_mp_pendiente(api_client, data)
    for estado in ("rechazado", "perdido"):
        run(
            insertar_cobro_db(
                session_factory,
                consultorio_id=data["consultorio_id"],
                paciente_id=data["paciente_os_demo"].id,
                tipo="tratamiento",
                medio="efectivo",
                estado=estado,
                monto="1000.00",
                presupuesto_id=data["presupuesto_cobro"],
            )
        )
    for cobro_id in (pendiente["id"],):
        respuesta = _reembolsar(api_client, data, cobro_id)
        assert respuesta.status_code == 409, respuesta.text

    async def ids_no_aprobados():
        from sqlalchemy import select

        from app.models.caja import Cobro

        async with session_factory() as session:
            return list(
                await session.scalars(
                    select(Cobro.id).where(
                        Cobro.estado.in_(("rechazado", "perdido"))
                    )
                )
            )

    for cobro_id in run(ids_no_aprobados()):
        assert _reembolsar(api_client, data, cobro_id).status_code == 409


def test_reembolso_inexistente_o_de_otro_consultorio_404(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    assert _reembolsar(api_client, data, uuid.uuid4()).status_code == 404

    async def crear_ajeno() -> uuid.UUID:
        ajeno = await otro_consultorio(session_factory)
        return await insertar_cobro_db(
            session_factory,
            consultorio_id=ajeno["consultorio_id"],
            paciente_id=ajeno["paciente_id"],
            tipo="otro",
            medio="efectivo",
            estado="aprobado",
            monto="1000.00",
        )

    assert _reembolsar(api_client, data, run(crear_ajeno())).status_code == 404


def test_reembolso_no_llama_al_proveedor(api_client, session_factory) -> None:
    """Expected: MP sandbox refunds only change state, never call the gateway."""
    data = _setup(session_factory)
    cobro_id = run(
        insertar_cobro_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_os_demo"].id,
            tipo="otro",
            medio="mercadopago",
            estado="aprobado",
            monto="8000.00",
            proveedor_pago_id="mp-refund-1",
        )
    )
    with mp_override(FailingMercadoPago()):
        respuesta = _reembolsar(api_client, data, cobro_id)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "reembolsado"
    assert run(movimientos_de(session_factory, cobro_id)) == []


def test_reembolso_por_recepcion_200(api_client, session_factory) -> None:
    data = _setup(session_factory)
    cobro = _crear(api_client, data)
    respuesta = _reembolsar(
        api_client, data, cobro["id"], actor="recepcionista"
    )
    assert respuesta.status_code == 200, respuesta.text


def test_listado_con_filtros_declarados_y_ficha(
    api_client, session_factory
) -> None:
    """Expected: declared filters narrow the list and the detail returns 200."""
    data = _setup(session_factory)
    efectivo = _crear(api_client, data, monto="1000.00")
    pendiente = _crear_mp_pendiente(api_client, data)
    headers = bearer(data["actores"]["administrador"])

    def listar(**params):
        return api_client.get("/cobros", params=params, headers=headers)

    por_estado = listar(estado="aprobado")
    assert por_estado.status_code == 200
    assert {c["id"] for c in por_estado.json()} == {efectivo["id"]}

    por_medio = listar(medio="mercadopago")
    assert {c["id"] for c in por_medio.json()} == {pendiente["id"]}

    por_paciente = listar(paciente_id=str(data["paciente_os_demo"].id))
    assert {c["id"] for c in por_paciente.json()} == {
        efectivo["id"],
        pendiente["id"],
    }

    por_fecha = listar(
        fecha_desde=data["hoy"].isoformat(),
        fecha_hasta=data["hoy"].isoformat(),
    )
    assert {c["id"] for c in por_fecha.json()} == {
        efectivo["id"],
        pendiente["id"],
    }

    ficha = api_client.get(f"/cobros/{efectivo['id']}", headers=headers)
    assert ficha.status_code == 200
    assert ficha.json()["monto"] == "1000.00"


def test_listado_rechaza_filtro_no_declarado(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    respuesta = api_client.get(
        "/cobros",
        params={"minimo": "100"},
        headers=bearer(data["actores"]["administrador"]),
    )
    assert respuesta.status_code == 422, respuesta.text

    ficha = api_client.get(
        f"/cobros/{uuid.uuid4()}",
        params={"extra": "1"},
        headers=bearer(data["actores"]["administrador"]),
    )
    assert ficha.status_code == 422, ficha.text
