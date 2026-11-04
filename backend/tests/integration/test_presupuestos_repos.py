"""Budget repositories: active-item reads and descending listings (C-12 D11)."""

from datetime import datetime, timedelta, timezone

from app.infrastructure.uow import UnitOfWork
from app.models import ItemPresupuesto
from tests.integration.helpers import run
from tests.integration.presupuestos_helpers import (
    insertar_item_db,
    insertar_presupuesto_db,
    setup_presupuestos,
)


def _setup(session_factory) -> dict[str, object]:
    return run(setup_presupuestos(session_factory))


def test_get_con_items_ignora_items_dados_de_baja(session_factory) -> None:
    """Expected: the detail only exposes live lines, never replaced ones."""
    data = _setup(session_factory)
    cons = data["prestaciones"]["CONS"]
    obt = data["prestaciones"]["OBT"]

    async def scenario() -> None:
        presupuesto_id = await insertar_presupuesto_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_os_demo"].id,
            profesional_id=data["profesional"].id,
            creado_por=data["actores"]["odontologo"].id,
        )
        activo = await insertar_item_db(
            session_factory,
            presupuesto_id=presupuesto_id,
            prestacion_id=cons.id,
        )
        reemplazado = await insertar_item_db(
            session_factory,
            presupuesto_id=presupuesto_id,
            prestacion_id=obt.id,
            pieza=16,
            precio_unitario="25000.00",
            cobertura_item="15000.00",
            copago_item="10000.00",
        )

        async with UnitOfWork(session_factory) as uow:
            reemplazado_model = await uow.items_presupuesto.get(reemplazado)
            assert reemplazado_model is not None
            await uow.items_presupuesto.soft_delete(reemplazado_model)
            # The replacement line arrives after the soft delete.
            nuevo = await uow.items_presupuesto.add(
                ItemPresupuesto(
                    presupuesto_id=presupuesto_id,
                    prestacion_id=cons.id,
                    cantidad=1,
                    precio_unitario="10000.00",
                    cobertura_item="6000.00",
                    copago_item="4000.00",
                )
            )
            nuevo_id = nuevo.id

        async with UnitOfWork(session_factory) as uow:
            presupuesto, items = await uow.presupuestos.get_con_items(
                presupuesto_id
            )
            assert presupuesto is not None
            assert presupuesto.id == presupuesto_id
            assert {item.id for item in items} == {activo, nuevo_id}
            assert reemplazado not in {item.id for item in items}

    run(scenario())


def test_listado_filtrado_por_paciente_profesional_y_estado(
    session_factory,
) -> None:
    """Expected: filters narrow the list and `created_at` is descending."""
    data = _setup(session_factory)
    base = datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc)

    async def scenario() -> None:
        propio = data["paciente_os_demo"].id
        otro = data["paciente_ajeno"].id
        profesional = data["profesional"].id
        ajeno = data["profesional_ajeno"].id

        viejo = await insertar_presupuesto_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=propio,
            profesional_id=profesional,
            creado_por=data["actores"]["odontologo"].id,
            estado="borrador",
            creado_en=base,
        )
        nuevo = await insertar_presupuesto_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=propio,
            profesional_id=profesional,
            creado_por=data["actores"]["odontologo"].id,
            estado="aceptado",
            creado_en=base + timedelta(days=1),
        )
        ajeno_id = await insertar_presupuesto_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=otro,
            profesional_id=ajeno,
            creado_por=data["actores"]["odontologo"].id,
            estado="finalizado",
            creado_en=base + timedelta(days=2),
        )

        async with UnitOfWork(session_factory) as uow:
            por_paciente = await uow.presupuestos.list_filtrado(
                data["consultorio_id"], paciente_id=propio
            )
            assert [p.id for p in por_paciente] == [nuevo, viejo]

            por_profesional = await uow.presupuestos.list_filtrado(
                data["consultorio_id"], profesional_id=ajeno
            )
            assert [p.id for p in por_profesional] == [ajeno_id]

            por_estado = await uow.presupuestos.list_filtrado(
                data["consultorio_id"], estado="borrador"
            )
            assert [p.id for p in por_estado] == [viejo]

            todos = await uow.presupuestos.list_filtrado(
                data["consultorio_id"]
            )
            assert [p.id for p in todos] == [ajeno_id, nuevo, viejo]

    run(scenario())


def test_baja_logica_de_items_reemplazados(session_factory) -> None:
    """Expected: replacing lines soft-deletes them, never removes history."""
    data = _setup(session_factory)
    cons = data["prestaciones"]["CONS"]

    async def scenario() -> None:
        presupuesto_id = await insertar_presupuesto_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            paciente_id=data["paciente_os_demo"].id,
            profesional_id=data["profesional"].id,
            creado_por=data["actores"]["odontologo"].id,
        )
        item_id = await insertar_item_db(
            session_factory,
            presupuesto_id=presupuesto_id,
            prestacion_id=cons.id,
        )

        async with UnitOfWork(session_factory) as uow:
            assert await uow.items_presupuesto.desactivar_de_presupuesto(
                presupuesto_id
            ) == 1
            activos = await uow.items_presupuesto.list_by_presupuesto(
                presupuesto_id
            )
            assert activos == []
            historicos = await uow.items_presupuesto.list_by_presupuesto(
                presupuesto_id, include_inactive=True
            )
            assert [item.id for item in historicos] == [item_id]
            assert historicos[0].is_active is False
            assert historicos[0].deleted_at is not None

    run(scenario())
