"""Clinical authorisation helpers: "propio" and "en sala" (C-11, tasks 3.3/3.4)."""

import uuid
from datetime import timedelta

import pytest

from app.application.clinica import paciente_en_sala, paciente_propio
from app.infrastructure.uow import UnitOfWork
from tests.integration.clinica_helpers import (
    INICIO_BASE,
    setup_clinica,
)
from tests.integration.helpers import run
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.turnos_helpers import insertar_turno_db


async def _paciente_con_turno(
    session_factory, data, *, hora: int, estado: str
):
    consultorio_id = data["consultorio_id"]
    paciente = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Estado",
        apellido=estado.title(),
        dni=f"43{hora:02d}{uuid.uuid4().int % 10000:04d}",
        telefono=f"+549117777{hora:04d}",
    )
    inicio = INICIO_BASE + timedelta(hours=hora)
    await insertar_turno_db(
        session_factory,
        consultorio_id=consultorio_id,
        paciente_id=paciente.id,
        profesional_id=data["profesional"].id,
        sillon_id=data["sillon"].id,
        inicio=inicio,
        fin=inicio + timedelta(hours=1),
        estado=estado,
    )
    return paciente


@pytest.mark.parametrize(
    "estado", ["reservado", "confirmado", "en_sala", "atendido"]
)
def test_paciente_propio_con_turno_activo(session_factory, estado: str) -> None:
    """A live turn of the linked professional grants access."""

    async def scenario() -> None:
        data = await setup_clinica(session_factory)
        paciente = await _paciente_con_turno(
            session_factory, data, hora=14, estado=estado
        )
        async with UnitOfWork(session_factory) as uow:
            assert (
                await paciente_propio(
                    uow, data["actores"]["odontologo"], paciente.id
                )
                is True
            )

    run(scenario())


@pytest.mark.parametrize("estado", ["cancelado", "ausente"])
def test_turno_cancelado_o_ausente_no_otorga_propiedad(
    session_factory, estado: str
) -> None:
    """Business rule: a cancelled/no-show turn is not a live clinical link."""

    async def scenario() -> None:
        data = await setup_clinica(session_factory)
        paciente = await _paciente_con_turno(
            session_factory, data, hora=15, estado=estado
        )
        async with UnitOfWork(session_factory) as uow:
            assert (
                await paciente_propio(
                    uow, data["actores"]["odontologo"], paciente.id
                )
                is False
            )

    run(scenario())


def test_paciente_ajeno_no_es_propio(session_factory) -> None:
    """The patient is attended by another professional: no access."""

    async def scenario() -> None:
        data = await setup_clinica(session_factory)
        async with UnitOfWork(session_factory) as uow:
            assert (
                await paciente_propio(
                    uow,
                    data["actores"]["odontologo"],
                    data["paciente_ajeno"].id,
                )
                is False
            )

    run(scenario())


def test_odontologo_sin_profesional_no_tiene_pacientes(session_factory) -> None:
    """Edge: a dentist user without a `profesionales` row owns nothing."""

    async def scenario() -> None:
        data = await setup_clinica(session_factory)
        async with UnitOfWork(session_factory) as uow:
            assert (
                await paciente_propio(
                    uow,
                    data["odontologo_sin_profesional"],
                    data["paciente_propio"].id,
                )
                is False
            )

    run(scenario())


def test_paciente_en_sala_solo_con_turno_en_sala(session_factory) -> None:
    """Assistant access is limited to the patient currently in the chair."""

    async def scenario() -> None:
        data = await setup_clinica(session_factory)
        async with UnitOfWork(session_factory) as uow:
            assert (
                await paciente_en_sala(uow, data["paciente_en_sala"].id)
                is True
            )
            assert (
                await paciente_en_sala(uow, data["paciente_propio"].id)
                is False
            )
            assert (
                await paciente_en_sala(uow, data["paciente_ajeno"].id)
                is False
            )
            assert (
                await paciente_en_sala(uow, data["paciente_cancelado"].id)
                is False
            )
            assert (
                await paciente_en_sala(uow, data["paciente_sin_turno"].id)
                is False
            )

    run(scenario())
