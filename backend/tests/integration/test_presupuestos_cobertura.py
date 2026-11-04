"""Local coverage provider: the D4 decision matrix without external calls."""

import uuid
from decimal import Decimal

from app.application.presupuestos import LocalCoberturaProvider
from app.infrastructure.uow import UnitOfWork
from tests.integration.helpers import run
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.presupuestos_helpers import (
    crear_convenio,
    setup_presupuestos,
)


def _setup(session_factory) -> dict[str, object]:
    return run(setup_presupuestos(session_factory))


def test_paciente_sin_obra_social_tiene_cobertura_cero_conocida(
    session_factory,
) -> None:
    """No agreement is a known 0 %, not an unverifiable coverage."""
    data = _setup(session_factory)

    async def scenario() -> None:
        async with UnitOfWork(session_factory) as uow:
            paciente = await uow.pacientes.get(data["paciente_propio"].id)
            assert paciente is not None
            cobertura = await LocalCoberturaProvider().resolver(uow, paciente)
        assert cobertura is not None
        assert cobertura.cobertura_porcentaje == Decimal("0")
        assert cobertura.cubre("CONS") is False

    run(scenario())


def test_convenio_activo_con_porcentaje_y_lista_de_prestaciones(
    session_factory,
) -> None:
    """OS Demo: 60 % and only the listed codes are covered."""
    data = _setup(session_factory)

    async def scenario() -> None:
        async with UnitOfWork(session_factory) as uow:
            paciente = await uow.pacientes.get(data["paciente_os_demo"].id)
            assert paciente is not None
            cobertura = await LocalCoberturaProvider().resolver(uow, paciente)
        assert cobertura is not None
        assert cobertura.cobertura_porcentaje == Decimal("60")
        assert cobertura.cubre("CONS") is True
        assert cobertura.cubre("OBT") is True
        assert cobertura.cubre("EXO") is False

    run(scenario())


def test_prestacion_fuera_de_la_lista_no_se_cubre(session_factory) -> None:
    data = _setup(session_factory)

    async def scenario() -> None:
        async with UnitOfWork(session_factory) as uow:
            paciente = await uow.pacientes.get(data["paciente_os_demo"].id)
            assert paciente is not None
            cobertura = await LocalCoberturaProvider().resolver(uow, paciente)
        assert cobertura is not None
        assert cobertura.cubre("EXO") is False

    run(scenario())


def test_convenio_sin_porcentaje_no_es_verificable(session_factory) -> None:
    data = _setup(session_factory)

    async def scenario() -> None:
        async with UnitOfWork(session_factory) as uow:
            paciente = await uow.pacientes.get(
                data["paciente_sin_porcentaje"].id
            )
            assert paciente is not None
            cobertura = await LocalCoberturaProvider().resolver(uow, paciente)
        assert cobertura is None

    run(scenario())


def test_convenio_con_baja_logica_no_es_verificable(session_factory) -> None:
    data = _setup(session_factory)

    async def scenario() -> None:
        async with UnitOfWork(session_factory) as uow:
            paciente = await uow.pacientes.get(
                data["paciente_convenio_inactivo"].id
            )
            assert paciente is not None
            cobertura = await LocalCoberturaProvider().resolver(uow, paciente)
        assert cobertura is None

    run(scenario())


def test_reglas_no_interpretables_no_son_verificables(session_factory) -> None:
    """A percentage that is not a number makes the rules unusable."""
    data = _setup(session_factory)

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        for nombre, reglas in (
            ("OS Porcentaje Texto", {"cobertura_porcentaje": "sesenta"}),
            ("OS Porcentaje Negativo", {"cobertura_porcentaje": -1}),
            (
                "OS Lista Invalida",
                {
                    "cobertura_porcentaje": 60,
                    "prestaciones_cubiertas": "CONS",
                },
            ),
        ):
            obra = await crear_convenio(
                session_factory,
                consultorio_id,
                nombre=f"{nombre} {uuid.uuid4().hex[:6]}",
                reglas_cobertura=reglas,
            )
            paciente = await create_paciente(
                session_factory,
                consultorio_id,
                nombre="Reglas",
                apellido="Raras",
                dni=f"9{uuid.uuid4().int % 10_000_000:07d}",
                telefono="+5491177770299",
                obra_social_id=obra.id,
                nro_afiliado="RR-0299",
            )
            async with UnitOfWork(session_factory) as uow:
                paciente_db = await uow.pacientes.get(paciente.id)
                assert paciente_db is not None
                cobertura = await LocalCoberturaProvider().resolver(
                    uow, paciente_db
                )
            assert cobertura is None, nombre

    run(scenario())
