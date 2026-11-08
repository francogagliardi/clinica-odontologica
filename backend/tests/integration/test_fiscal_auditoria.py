"""C-14 group 10.5: fiscal/settlement audit trail and append-only guard."""

import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.application.comprobantes import procesar_comprobante
from app.infrastructure.arca import TestArcaClient
from app.models import RegistroAuditoria
from tests.integration.clinica_helpers import auditorias
from tests.integration.comprobantes_helpers import (
    comprobante_de_cobro,
    crear_comprobante_pendiente,
    fiscal_config,
    post_efectivo,
    setup_comprobantes,
)
from tests.integration.helpers import run, sqlstate
from tests.integration.liquidaciones_helpers import (
    crear_escenario,
    post_liquidacion,
    setup_liquidaciones,
)
from tests.integration.recursos_helpers import bearer

_UA_COMPROBANTE = "pytest-ua-c14"
_UA_LIQUIDACION = "pytest-ua-c14-liq"


def _setup_comprobantes(session_factory) -> dict[str, object]:
    return run(setup_comprobantes(session_factory))


def _setup_liquidaciones(session_factory) -> dict[str, object]:
    return run(setup_liquidaciones(session_factory))


def test_auditoria_de_comprobantes_con_usuario_y_actor_sistema(
    api_client, session_factory
) -> None:
    data = _setup_comprobantes(session_factory)
    body = post_efectivo(api_client, data, actor="administrador")

    async def comprobante():
        return await comprobante_de_cobro(
            session_factory, uuid.UUID(body["id"])
        )

    creado = run(comprobante())
    assert creado is not None

    crear = run(auditorias(session_factory, "comprobante.crear"))
    assert len(crear) == 1
    assert crear[0].usuario_id == data["actores"]["administrador"].id
    assert crear[0].ip == "testclient"
    assert crear[0].dispositivo == _UA_COMPROBANTE

    emitido = run(
        procesar_comprobante(
            session_factory,
            TestArcaClient(),
            creado.id,
            config=fiscal_config(),
        )
    )
    assert emitido is not None and emitido.estado == "emitido"
    emitir = run(auditorias(session_factory, "comprobante.emitir"))
    assert len(emitir) == 1
    assert emitir[0].usuario_id is None
    assert emitir[0].entidad_id == str(creado.id)

    respuesta = api_client.post(
        f"/comprobantes/{creado.id}/enviar",
        json={"canal": "whatsapp"},
        headers=bearer(data["actores"]["recepcionista"]),
    )
    assert respuesta.status_code == 201, respuesta.text
    enviar = run(auditorias(session_factory, "comprobante.enviar"))
    assert len(enviar) == 1
    assert enviar[0].usuario_id == data["actores"]["recepcionista"].id
    assert enviar[0].ip == "testclient"


def test_auditoria_de_emision_fallida_y_reintento(
    api_client, session_factory
) -> None:
    data = _setup_comprobantes(session_factory)
    comprobante_id = run(
        crear_comprobante_pendiente(session_factory, data)
    )
    cliente = TestArcaClient()
    cliente.simular_fallo(1)
    fallido = run(
        procesar_comprobante(
            session_factory,
            cliente,
            comprobante_id,
            config=fiscal_config(max_intentos=5),
        )
    )
    assert fallido is not None and fallido.estado == "pendiente"

    fallo = run(auditorias(session_factory, "comprobante.emitir_fallido"))
    assert len(fallo) == 1
    assert fallo[0].usuario_id is None

    respuesta = api_client.post(
        f"/comprobantes/{comprobante_id}/reintentar",
        headers=bearer(data["actores"]["administrador"]),
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "pendiente"
    reintento = run(auditorias(session_factory, "comprobante.reintentar"))
    assert len(reintento) == 1
    assert reintento[0].usuario_id == data["actores"]["administrador"].id
    assert reintento[0].ip == "testclient"


def test_auditoria_de_liquidaciones(
    api_client, session_factory
) -> None:
    data = _setup_liquidaciones(session_factory)
    run(crear_escenario(session_factory, data))
    creada = post_liquidacion(api_client, data)
    assert creada.status_code == 201, creada.text
    liquidacion_id = creada.json()["id"]

    edicion = api_client.put(
        f"/obras-sociales/liquidaciones/{liquidacion_id}",
        json={"observaciones": "revisada"},
        headers={
            **bearer(data["actores"]["recepcionista"]),
            "User-Agent": _UA_LIQUIDACION,
        },
    )
    assert edicion.status_code == 200, edicion.text

    cierre = api_client.post(
        f"/obras-sociales/liquidaciones/{liquidacion_id}/cerrar",
        headers={
            **bearer(data["actores"]["administrador"]),
            "User-Agent": _UA_LIQUIDACION,
        },
    )
    assert cierre.status_code == 200, cierre.text

    run(
        crear_escenario(
            session_factory,
            data,
            fecha_cobro=date(2026, 12, 5),
        )
    )
    borrador = post_liquidacion(
        api_client,
        data,
        desde=date(2026, 12, 1),
        hasta=date(2026, 12, 31),
    )
    assert borrador.status_code == 201, borrador.text
    borrado = api_client.delete(
        f"/obras-sociales/liquidaciones/{borrador.json()['id']}",
        headers={
            **bearer(data["actores"]["administrador"]),
            "User-Agent": _UA_LIQUIDACION,
        },
    )
    assert borrado.status_code == 204, borrado.text

    crear = run(auditorias(session_factory, "liquidacion.crear"))
    assert len(crear) == 2
    assert all(
        fila.usuario_id == data["actores"]["administrador"].id
        for fila in crear
    )
    editar = run(auditorias(session_factory, "liquidacion.editar"))
    assert len(editar) == 1
    assert editar[0].usuario_id == data["actores"]["recepcionista"].id
    cerrar = run(auditorias(session_factory, "liquidacion.cerrar"))
    assert len(cerrar) == 1
    assert cerrar[0].usuario_id == data["actores"]["administrador"].id
    eliminar = run(auditorias(session_factory, "liquidacion.eliminar"))
    assert len(eliminar) == 1
    assert eliminar[0].usuario_id == data["actores"]["administrador"].id
    for fila in (*crear, *editar, *cerrar, *eliminar):
        assert fila.ip == "testclient"
        assert fila.dispositivo == _UA_LIQUIDACION


def test_escritura_rechazada_no_deja_auditoria(
    api_client, session_factory
) -> None:
    data = _setup_liquidaciones(session_factory)
    sin_practicas = post_liquidacion(api_client, data)
    assert sin_practicas.status_code == 422, sin_practicas.text
    assert run(auditorias(session_factory, "liquidacion.crear")) == []

    run(crear_escenario(session_factory, data))
    primero = post_liquidacion(api_client, data)
    assert primero.status_code == 201, primero.text
    solapada = post_liquidacion(api_client, data)
    assert solapada.status_code == 409, solapada.text
    assert len(run(auditorias(session_factory, "liquidacion.crear"))) == 1


async def _sqlstate_de(session_factory, statement: str, params) -> str | None:
    try:
        async with session_factory() as session, session.begin():
            await session.execute(text(statement), params)
    except DBAPIError as error:
        return sqlstate(error)
    return None


def test_auditoria_es_append_only(session_factory) -> None:
    """Business rule: PostgreSQL rejects UPDATE/DELETE with P0001."""

    async def crear() -> RegistroAuditoria:
        async with session_factory() as session, session.begin():
            registro = RegistroAuditoria(
                accion="comprobante.crear",
                entidad="comprobante",
                entidad_id=str(uuid.uuid4()),
            )
            session.add(registro)
            await session.flush()
            return registro

    registro = run(crear())
    assert (
        run(
            _sqlstate_de(
                session_factory,
                "UPDATE registro_auditoria SET accion = 'x' WHERE id = :id",
                {"id": registro.id},
            )
        )
        == "P0001"
    )
    assert (
        run(
            _sqlstate_de(
                session_factory,
                "DELETE FROM registro_auditoria WHERE id = :id",
                {"id": registro.id},
            )
        )
        == "P0001"
    )
