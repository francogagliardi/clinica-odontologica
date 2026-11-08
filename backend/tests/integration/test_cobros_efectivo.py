"""C-13 cash payments: 201 with movement, strict body, 404/409 (group 5)."""

import uuid
from datetime import date

from sqlalchemy import func, select, text

from app.models.caja import Cobro
from tests.integration.cobros_helpers import (
    cerrar_caja_db,
    cobro_payload,
    movimientos_de,
    setup_cobros,
)
from tests.integration.helpers import run
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.recursos_helpers import bearer

_UA = "pytest-ua-c13-efectivo"


def _setup(session_factory, *, con_caja: bool = True) -> dict[str, object]:
    return run(setup_cobros(session_factory, con_caja=con_caja))


def _post(api_client, data, *, actor: str = "recepcionista", **overrides):
    return api_client.post(
        "/cobros",
        json=cobro_payload(data, **overrides),
        headers={**bearer(data["actores"][actor]), "User-Agent": _UA},
    )


def _contar(session_factory) -> int:
    async def contar() -> int:
        async with session_factory() as session:
            return await session.scalar(
                select(func.count()).select_from(Cobro)
            )

    return run(contar())


def test_cobro_efectivo_aprobado_deja_movimiento(
    api_client, session_factory
) -> None:
    """Expected: 201 approved in the local day plus one cash income movement."""
    data = _setup(session_factory)
    respuesta = _post(
        api_client,
        data,
        tipo="otro",
        medio="efectivo",
        monto="15000.00",
    )
    assert respuesta.status_code == 201, respuesta.text
    body = respuesta.json()
    assert body["estado"] == "aprobado"
    assert body["tipo"] == "otro"
    assert body["medio"] == "efectivo"
    assert body["monto"] == "15000.00"
    assert date.fromisoformat(body["fecha_operacion"]) == data["hoy"]
    assert body["saldo_pendiente"] is None

    movimientos = run(movimientos_de(session_factory, uuid.UUID(body["id"])))
    assert len(movimientos) == 1
    movimiento = movimientos[0]
    assert movimiento.tipo == "ingreso"
    assert movimiento.medio == "efectivo"
    assert movimiento.monto == 15000
    assert movimiento.caja_id == data["caja_id"]
    assert movimiento.creado_por == data["actores"]["recepcionista"].id


def test_monto_no_positivo_no_crea_nada(api_client, session_factory) -> None:
    """Business error: 0 and negative amounts are 422 and leave no row."""
    data = _setup(session_factory)
    for monto in ("0", "-1.00"):
        respuesta = _post(api_client, data, monto=monto)
        assert respuesta.status_code == 422, respuesta.text
    assert _contar(session_factory) == 0


def test_campo_no_declarado_devuelve_422(api_client, session_factory) -> None:
    """Business error: estado/moneda/extra fields are rejected, never ignored."""
    data = _setup(session_factory)
    for extra in (
        {"moneda": "USD"},
        {"estado": "aprobado"},
        {"precio": "1.00"},
    ):
        respuesta = _post(api_client, data, **extra)
        assert respuesta.status_code == 422, respuesta.text
    assert _contar(session_factory) == 0


def test_paciente_inexistente_o_inactivo_devuelve_404(
    api_client, session_factory
) -> None:
    """Business error: unknown/soft-deleted patients are 404."""
    data = _setup(session_factory)
    inexistente = _post(api_client, data, paciente_id=uuid.uuid4())
    assert inexistente.status_code == 404

    async def desactivar() -> None:
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "UPDATE pacientes SET is_active = false, "
                    "deleted_at = now() WHERE id = :id"
                ),
                {"id": data["paciente_os_demo"].id},
            )

    run(desactivar())
    inactivo = _post(api_client, data)
    assert inactivo.status_code == 404
    assert _contar(session_factory) == 0


def test_paciente_de_otro_consultorio_devuelve_404(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)

    async def crear_ajeno() -> uuid.UUID:
        from tests.integration.clinica_helpers import otro_consultorio

        ajeno = await otro_consultorio(session_factory)
        return ajeno["paciente_id"]

    paciente_ajeno = run(crear_ajeno())
    respuesta = _post(api_client, data, paciente_id=paciente_ajeno)
    assert respuesta.status_code == 404
    assert _contar(session_factory) == 0


def test_caja_cerrada_devuelve_409(api_client, session_factory) -> None:
    """Business error: a closed register never receives a cash payment."""
    data = _setup(session_factory)
    run(
        cerrar_caja_db(
            session_factory,
            data["consultorio_id"],
            data["actores"]["administrador"].id,
        )
    )
    respuesta = _post(api_client, data)
    assert respuesta.status_code == 409, respuesta.text
    assert _contar(session_factory) == 0


def test_sin_caja_abierta_devuelve_409_y_no_la_crea(
    api_client, session_factory
) -> None:
    """Business error: cash never creates the day's register implicitly."""
    data = _setup(session_factory, con_caja=False)
    respuesta = _post(api_client, data)
    assert respuesta.status_code == 409, respuesta.text
    assert _contar(session_factory) == 0

    async def contar_cajas() -> int:
        async with session_factory() as session:
            return await session.scalar(
                text("SELECT count(*) FROM cajas_diarias")
            )

    assert run(contar_cajas()) == 0


def test_paciente_activo_de_otro_es_alta_valida(
    api_client, session_factory
) -> None:
    """Edge: the patient is the reference, not the user who charges."""
    data = _setup(session_factory)
    paciente = run(
        create_paciente(
            session_factory,
            data["consultorio_id"],
            nombre="Nuevo",
            apellido="Paciente",
            dni="42999001",
            telefono="+5491177779901",
        )
    )
    respuesta = _post(api_client, data, paciente_id=paciente.id)
    assert respuesta.status_code == 201, respuesta.text
