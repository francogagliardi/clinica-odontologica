"""C-15 `ExportacionRepository`: CRUD, in-progress combination, claim and sweep.

The durable job is the row, not the Redis message (design D3): these tests
exercise the PostgreSQL contract the worker relies on.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.infrastructure.uow import UnitOfWork
from app.models import Exportacion
from tests.integration.helpers import run
from tests.integration.reportes_helpers import (
    insertar_exportacion_db,
    setup_exportaciones,
)


def test_alta_get_y_listado_filtrado(session_factory) -> None:
    """Expected: the row survives the unit of work and filters are exact."""
    data = run(setup_exportaciones(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        solicitado_por = data["actores"]["administrador"].id
        paciente_id = data["paciente"].id

        async with UnitOfWork(session_factory) as uow:
            creada = await uow.exportaciones.add(
                Exportacion(
                    consultorio_id=consultorio_id,
                    solicitado_por=solicitado_por,
                    alcance="paciente",
                    paciente_id=paciente_id,
                )
            )
            assert creada.id is not None

        async with UnitOfWork(session_factory) as uow:
            leida = await uow.exportaciones.get(creada.id)
            assert leida is not None
            assert leida.alcance == "paciente"
            assert leida.paciente_id == paciente_id
            assert leida.estado == "pendiente"
            assert leida.contenido is None

        consultorio_job = await insertar_exportacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            alcance="consultorio",
        )
        lista_job = await insertar_exportacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=data["actores"]["odontologo"].id,
            alcance="paciente",
            paciente_id=paciente_id,
            estado="lista",
        )

        async with UnitOfWork(session_factory) as uow:
            por_alcance = await uow.exportaciones.list_filtrado(
                consultorio_id, alcance="consultorio"
            )
            assert {fila.id for fila in por_alcance} == {consultorio_job}

            por_estado = await uow.exportaciones.list_filtrado(
                consultorio_id, estado="lista"
            )
            assert {fila.id for fila in por_estado} == {lista_job}

            por_solicitante = await uow.exportaciones.list_filtrado(
                consultorio_id, solicitado_por=solicitado_por
            )
            assert {fila.id for fila in por_solicitante} == {
                creada.id,
                consultorio_job,
            }

        otro_consultorio = uuid.uuid4()
        async with UnitOfWork(session_factory) as uow:
            ajenas = await uow.exportaciones.list_filtrado(otro_consultorio)
            assert ajenas == []

    run(scenario())


def test_exportacion_en_curso_solo_pendiente_o_generando(
    session_factory,
) -> None:
    """Expected: a `lista` row of the same combination never blocks a retry."""
    data = run(setup_exportaciones(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        solicitado_por = data["actores"]["administrador"].id
        paciente_id = data["paciente"].id

        pendiente_id = await insertar_exportacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=solicitado_por,
            alcance="paciente",
            paciente_id=paciente_id,
        )

        async with UnitOfWork(session_factory) as uow:
            encontrada = await uow.exportaciones.get_en_curso(
                consultorio_id=consultorio_id,
                solicitado_por=solicitado_por,
                alcance="paciente",
                paciente_id=paciente_id,
            )
            assert encontrada is not None
            assert encontrada.id == pendiente_id

            otro_alcance = await uow.exportaciones.get_en_curso(
                consultorio_id=consultorio_id,
                solicitado_por=solicitado_por,
                alcance="consultorio",
                paciente_id=None,
            )
            assert otro_alcance is None

        # Once it is `lista`, the same combination does not count as in progress.
        async with session_factory() as session, session.begin():
            session.add(
                Exportacion(
                    consultorio_id=consultorio_id,
                    solicitado_por=solicitado_por,
                    alcance="paciente",
                    paciente_id=paciente_id,
                    estado="lista",
                    contenido=b"PK-listo",
                    tamano_bytes=9,
                    generada_at=datetime.now(timezone.utc),
                )
            )
            await session.flush()

        async with UnitOfWork(session_factory) as uow:
            sigue = await uow.exportaciones.get_en_curso(
                consultorio_id=consultorio_id,
                solicitado_por=solicitado_por,
                alcance="paciente",
                paciente_id=paciente_id,
            )
            assert sigue is not None
            assert sigue.id == pendiente_id  # the pending one, not the list

        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "UPDATE exportaciones SET estado = 'fallida', "
                    "ultimo_error = 'fin del test' WHERE id = :id"
                ),
                {"id": pendiente_id},
            )

        async with UnitOfWork(session_factory) as uow:
            assert (
                await uow.exportaciones.get_en_curso(
                    consultorio_id=consultorio_id,
                    solicitado_por=solicitado_por,
                    alcance="paciente",
                    paciente_id=paciente_id,
                )
                is None
            )

    run(scenario())


def test_claim_con_token_vence_y_no_se_reclama_dos_veces(
    session_factory,
) -> None:
    """Expected: only one worker owns the row and the claim expires."""
    data = run(setup_exportaciones(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        ahora = datetime.now(timezone.utc)

        pendiente_id = await insertar_exportacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=data["actores"]["administrador"].id,
            alcance="consultorio",
        )
        token = uuid.uuid4()
        async with UnitOfWork(session_factory) as uow:
            reclamada = await uow.exportaciones.reclamar(
                pendiente_id,
                token=token,
                ahora=ahora,
                claim_timeout_seconds=300,
            )
            assert reclamada is not None
            assert reclamada.id == pendiente_id
            assert reclamada.estado == "generando"
            assert reclamada.claim_token == token
            assert reclamada.reclamado_at is not None

        async with UnitOfWork(session_factory) as uow:
            segunda = await uow.exportaciones.reclamar(
                pendiente_id,
                token=uuid.uuid4(),
                ahora=ahora + timedelta(seconds=10),
                claim_timeout_seconds=300,
            )
            assert segunda is None

        # A claim older than the timeout is stealable (the worker died).
        vencida_id = await insertar_exportacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=data["actores"]["odontologo"].id,
            alcance="consultorio",
            reclamado_at=ahora - timedelta(minutes=10),
            claim_token=uuid.uuid4(),
        )
        nuevo_token = uuid.uuid4()
        async with UnitOfWork(session_factory) as uow:
            robada = await uow.exportaciones.reclamar(
                vencida_id,
                token=nuevo_token,
                ahora=ahora,
                claim_timeout_seconds=300,
            )
            assert robada is not None
            assert robada.claim_token == nuevo_token
            assert robada.estado == "generando"

        # Backoff not elapsed: not claimable yet.
        futura_id = await insertar_exportacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=data["actores"]["recepcionista"].id,
            alcance="consultorio",
            proximo_intento=ahora + timedelta(hours=1),
        )
        async with UnitOfWork(session_factory) as uow:
            assert (
                await uow.exportaciones.reclamar(
                    futura_id,
                    token=uuid.uuid4(),
                    ahora=ahora,
                    claim_timeout_seconds=300,
                )
                is None
            )

    run(scenario())


def test_pendientes_vencidos_para_el_barrido(session_factory) -> None:
    """Expected: due rows and stale claims, never future or freshly claimed."""
    data = run(setup_exportaciones(session_factory))

    async def scenario() -> None:
        consultorio_id = data["consultorio_id"]
        actores = data["actores"]
        ahora = datetime.now(timezone.utc)

        due = await insertar_exportacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=actores["administrador"].id,
            alcance="consultorio",
        )
        futura = await insertar_exportacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=actores["odontologo"].id,
            alcance="consultorio",
            proximo_intento=ahora + timedelta(hours=1),
        )
        reciente = await insertar_exportacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=actores["recepcionista"].id,
            alcance="consultorio",
            reclamado_at=ahora - timedelta(seconds=30),
        )
        vieja = await insertar_exportacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=actores["auditor"].id,
            alcance="consultorio",
            reclamado_at=ahora - timedelta(minutes=10),
        )
        await insertar_exportacion_db(
            session_factory,
            consultorio_id=consultorio_id,
            solicitado_por=actores["administrador"].id,
            alcance="paciente",
            paciente_id=data["paciente"].id,
            estado="lista",
        )

        async with UnitOfWork(session_factory) as uow:
            pendientes = await uow.exportaciones.list_pendientes_vencidos(
                ahora, limite=10, claim_timeout_seconds=300
            )
            assert {fila.id for fila in pendientes} == {due, vieja}
            assert futura not in {fila.id for fila in pendientes}
            assert reciente not in {fila.id for fila in pendientes}

            limitado = await uow.exportaciones.list_pendientes_vencidos(
                ahora, limite=1, claim_timeout_seconds=300
            )
            assert len(limitado) == 1

    run(scenario())
