"""Clinical repositories under a real PostgreSQL (C-11, task 3.1).

The invariants tested here are the ones the API relies on: one active history
per patient, one active rectification per signed evolution, a gapless next
odontogram version, and listings scoped to their owner.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.infrastructure.uow import UnitOfWork
from app.models import (
    Adjunto,
    Consentimiento,
    Evolucion,
    HistoriaClinica,
    Odontograma,
)
from tests.integration.helpers import run, sqlstate
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.clinica_helpers import setup_clinica


async def _historia(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    paciente_id: uuid.UUID,
    abierta_por: uuid.UUID,
) -> HistoriaClinica:
    historia = HistoriaClinica(
        consultorio_id=consultorio_id,
        paciente_id=paciente_id,
        abierta_por=abierta_por,
    )
    return await uow.historias.add(historia)


def test_historia_activa_unica_por_paciente(session_factory) -> None:
    """Business rule: a second active history is rejected with 23505."""

    async def scenario() -> None:
        data = await setup_clinica(session_factory)
        paciente = data["paciente_propio"]
        actores = data["actores"]

        async with UnitOfWork(session_factory) as uow:
            historia = await _historia(
                uow,
                consultorio_id=data["consultorio_id"],
                paciente_id=paciente.id,
                abierta_por=actores["odontologo"].id,
            )
            historia_id = historia.id

        async with UnitOfWork(session_factory) as uow:
            encontrada = await uow.historias.get_activa_por_paciente(
                paciente.id
            )
            assert encontrada is not None
            assert encontrada.id == historia_id

        with pytest.raises(IntegrityError) as error:
            async with UnitOfWork(session_factory) as uow:
                await _historia(
                    uow,
                    consultorio_id=data["consultorio_id"],
                    paciente_id=paciente.id,
                    abierta_por=actores["odontologo"].id,
                )
        assert sqlstate(error.value) == "23505"

    run(scenario())


def test_historia_dada_de_baja_libera_el_lugar(session_factory) -> None:
    """Edge: the partial index only covers active rows."""

    async def scenario() -> None:
        data = await setup_clinica(session_factory)
        paciente = data["paciente_propio"]
        actores = data["actores"]

        async with UnitOfWork(session_factory) as uow:
            historia = await _historia(
                uow,
                consultorio_id=data["consultorio_id"],
                paciente_id=paciente.id,
                abierta_por=actores["odontologo"].id,
            )
            await uow.historias.soft_delete(historia)

        async with UnitOfWork(session_factory) as uow:
            assert (
                await uow.historias.get_activa_por_paciente(paciente.id)
                is None
            )
            nueva = await _historia(
                uow,
                consultorio_id=data["consultorio_id"],
                paciente_id=paciente.id,
                abierta_por=actores["odontologo"].id,
            )
            assert nueva.id != historia.id

    run(scenario())


def test_rectificatoria_unica_activa_por_evolucion(session_factory) -> None:
    """Business rule: one active rectification; a baja frees the slot."""

    async def scenario() -> None:
        data = await setup_clinica(session_factory)
        actores = data["actores"]
        profesional = data["profesional"]

        async with UnitOfWork(session_factory) as uow:
            historia = await _historia(
                uow,
                consultorio_id=data["consultorio_id"],
                paciente_id=data["paciente_propio"].id,
                abierta_por=actores["odontologo"].id,
            )
            original = await uow.evoluciones.add(
                Evolucion(
                    historia_id=historia.id,
                    profesional_id=profesional.id,
                    creado_por=actores["odontologo"].id,
                    texto="Original firmada",
                    fecha=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
                    firmada=True,
                    firmada_por=actores["odontologo"].id,
                    fecha_firma=datetime.now(timezone.utc),
                )
            )
            rectificatoria = await uow.evoluciones.add(
                Evolucion(
                    historia_id=historia.id,
                    profesional_id=profesional.id,
                    creado_por=actores["odontologo"].id,
                    texto="Rectificación",
                    fecha=datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc),
                    rectifica_a=original.id,
                )
            )
            original_id = original.id
            rectificatoria_id = rectificatoria.id

        async with UnitOfWork(session_factory) as uow:
            encontrada = await uow.evoluciones.get_rectificatoria_activa(
                original_id
            )
            assert encontrada is not None
            assert encontrada.id == rectificatoria_id
            listado = await uow.evoluciones.list_by_historia(historia.id)
            assert [fila.id for fila in listado][0] == rectificatoria_id

        with pytest.raises(IntegrityError) as error:
            async with UnitOfWork(session_factory) as uow:
                await uow.evoluciones.add(
                    Evolucion(
                        historia_id=historia.id,
                        profesional_id=profesional.id,
                        creado_por=actores["odontologo"].id,
                        texto="Segunda rectificación",
                        rectifica_a=original_id,
                    )
                )
        assert sqlstate(error.value) == "23505"

        async with UnitOfWork(session_factory) as uow:
            huerfana = await uow.evoluciones.get(rectificatoria_id)
            assert huerfana is not None
            await uow.evoluciones.soft_delete(huerfana)

        async with UnitOfWork(session_factory) as uow:
            nueva = await uow.evoluciones.add(
                Evolucion(
                    historia_id=historia.id,
                    profesional_id=profesional.id,
                    creado_por=actores["odontologo"].id,
                    texto="Rectificación posterior",
                    rectifica_a=original_id,
                )
            )
            assert nueva.id != rectificatoria_id

    run(scenario())


def test_proxima_version_del_odontograma(session_factory) -> None:
    """Expected: 1 without snapshots, then MAX(version) + 1."""

    async def scenario() -> None:
        data = await setup_clinica(session_factory)
        actores = data["actores"]

        async with UnitOfWork(session_factory) as uow:
            historia = await _historia(
                uow,
                consultorio_id=data["consultorio_id"],
                paciente_id=data["paciente_propio"].id,
                abierta_por=actores["odontologo"].id,
            )
            historia_id = historia.id
            assert await uow.odontogramas.proxima_version(historia_id) == 1
            await uow.odontogramas.add(
                Odontograma(historia_id=historia_id, version=1)
            )
            assert await uow.odontogramas.proxima_version(historia_id) == 2
            await uow.odontogramas.add(
                Odontograma(historia_id=historia_id, version=2)
            )
            assert await uow.odontogramas.proxima_version(historia_id) == 3
            vigente = await uow.odontogramas.get_vigente(historia_id)
            assert vigente is not None and vigente.version == 2

    run(scenario())


def test_listados_de_consentimientos_y_adjuntos(session_factory) -> None:
    """Expected: consents by patient (desc) and attachments by history."""

    async def scenario() -> None:
        data = await setup_clinica(session_factory)
        actores = data["actores"]
        consultorio_id = data["consultorio_id"]
        otro_paciente = await create_paciente(
            session_factory,
            consultorio_id,
            nombre="Listado",
            apellido="Clinica",
            dni="42111099",
            telefono="+5491177770199",
        )

        async with UnitOfWork(session_factory) as uow:
            historia = await _historia(
                uow,
                consultorio_id=consultorio_id,
                paciente_id=data["paciente_propio"].id,
                abierta_por=actores["odontologo"].id,
            )
            otra_historia = await _historia(
                uow,
                consultorio_id=consultorio_id,
                paciente_id=otro_paciente.id,
                abierta_por=actores["odontologo"].id,
            )
            await uow.consentimientos.add(
                Consentimiento(
                    consultorio_id=consultorio_id,
                    paciente_id=data["paciente_propio"].id,
                    tipo="procedimiento_invasivo",
                    texto_version="v1-2026-11",
                    texto_hash="a" * 64,
                    firma_ref="sha256:" + "b" * 64,
                    fecha=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
                    registrado_por=actores["odontologo"].id,
                )
            )
            await uow.consentimientos.add(
                Consentimiento(
                    consultorio_id=consultorio_id,
                    paciente_id=data["paciente_propio"].id,
                    tipo="procedimiento_invasivo",
                    texto_version="v1-2026-11",
                    texto_hash="c" * 64,
                    firma_ref="sha256:" + "d" * 64,
                    fecha=datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc),
                    registrado_por=actores["odontologo"].id,
                )
            )
            await uow.consentimientos.add(
                Consentimiento(
                    consultorio_id=consultorio_id,
                    paciente_id=otro_paciente.id,
                    tipo="procedimiento_invasivo",
                    texto_version="v1-2026-11",
                    texto_hash="e" * 64,
                    firma_ref="sha256:" + "f" * 64,
                    registrado_por=actores["odontologo"].id,
                )
            )
            await uow.adjuntos.add(
                Adjunto(
                    historia_id=historia.id,
                    nombre="foto.png",
                    mime="image/png",
                    tamano=8,
                    contenido=b"\x89PNG\r\n\x1a\n",
                    subido_por=actores["odontologo"].id,
                )
            )
            await uow.adjuntos.add(
                Adjunto(
                    historia_id=otra_historia.id,
                    nombre="otra.png",
                    mime="image/png",
                    tamano=8,
                    contenido=b"\x89PNG\r\n\x1a\n",
                    subido_por=actores["odontologo"].id,
                )
            )

        async with UnitOfWork(session_factory) as uow:
            consentimientos = (
                await uow.consentimientos.list_by_paciente(
                    data["paciente_propio"].id
                )
            )
            assert len(consentimientos) == 2
            assert consentimientos[0].fecha > consentimientos[1].fecha

            adjuntos = await uow.adjuntos.list_by_historia(historia.id)
            assert [adjunto.nombre for adjunto in adjuntos] == ["foto.png"]

    run(scenario())
