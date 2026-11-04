"""Builders for clinical-record integration tests (fictional data only)."""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.agenda import ARGENTINA_OFFSET
from app.models import Consultorio, RegistroAuditoria
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.recursos_helpers import (
    consultorio_demo_id,
    create_actor,
    create_profesional,
    create_sillon,
    seed_demo,
)
from tests.integration.turnos_helpers import insertar_turno_db

ROLES = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)

INICIO_BASE = datetime(2026, 11, 9, 9, 0, tzinfo=ARGENTINA_OFFSET)


async def setup_clinica(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Seed demo data plus every actor/scenario the clinical slice needs."""
    await seed_demo(session_factory)
    consultorio_id = await consultorio_demo_id(session_factory)
    actores = {
        rol: await create_actor(session_factory, rol) for rol in ROLES
    }
    profesional = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-CLINICA-1",
        usuario_id=actores["odontologo"].id,
    )
    odontologo_ajeno = await create_actor(
        session_factory,
        "odontologo",
        email="odonto.ajeno.clinica@clinica.test",
    )
    profesional_ajeno = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-CLINICA-2",
        usuario_id=odontologo_ajeno.id,
    )
    odontologo_sin_profesional = await create_actor(
        session_factory,
        "odontologo",
        email="odonto.sin.profesional@clinica.test",
    )
    sillon = await create_sillon(session_factory, consultorio_id, "Sillón C11")

    paciente_propio = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Propio",
        apellido="Clinica",
        dni="42111001",
        telefono="+5491177770101",
    )
    paciente_ajeno = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Ajeno",
        apellido="Clinica",
        dni="42111002",
        telefono="+5491177770102",
    )
    paciente_en_sala = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Sala",
        apellido="Clinica",
        dni="42111003",
        telefono="+5491177770103",
    )
    paciente_cancelado = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Cancelado",
        apellido="Clinica",
        dni="42111004",
        telefono="+5491177770104",
    )
    paciente_sin_turno = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="SinTurno",
        apellido="Clinica",
        dni="42111005",
        telefono="+5491177770105",
    )

    async def turno(
        paciente_id: uuid.UUID,
        profesional_id: uuid.UUID,
        hora: int,
        estado: str,
    ) -> uuid.UUID:
        inicio = INICIO_BASE + timedelta(hours=hora)
        return await insertar_turno_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            profesional_id=profesional_id,
            sillon_id=sillon.id,
            inicio=inicio,
            fin=inicio + timedelta(hours=1),
            estado=estado,
        )

    return {
        "consultorio_id": consultorio_id,
        "actores": actores,
        "profesional": profesional,
        "profesional_ajeno": profesional_ajeno,
        "odontologo_ajeno": odontologo_ajeno,
        "odontologo_sin_profesional": odontologo_sin_profesional,
        "sillon": sillon,
        "paciente_propio": paciente_propio,
        "paciente_ajeno": paciente_ajeno,
        "paciente_en_sala": paciente_en_sala,
        "paciente_cancelado": paciente_cancelado,
        "paciente_sin_turno": paciente_sin_turno,
        "turnos": {
            "propio": await turno(
                paciente_propio.id, profesional.id, 9, "reservado"
            ),
            "ajeno": await turno(
                paciente_ajeno.id, profesional_ajeno.id, 10, "confirmado"
            ),
            "en_sala": await turno(
                paciente_en_sala.id, profesional.id, 11, "en_sala"
            ),
            "cancelado": await turno(
                paciente_cancelado.id, profesional.id, 12, "cancelado"
            ),
        },
    }


async def otro_consultorio(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, uuid.UUID]:
    """A second tenant with its own patient, to prove cross-consultorio 404."""
    consultorio_id = uuid.uuid4()
    async with session_factory() as session, session.begin():
        session.add(
            Consultorio(
                id=consultorio_id,
                nombre="Consultorio Ajeno",
                slug=f"ajeno-{consultorio_id.hex[:8]}",
            )
        )
    paciente = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Otra",
        apellido="Clinica",
        dni=f"9{uuid.uuid4().int % 10_000_000:07d}",
        telefono="+5491177770199",
    )
    return {
        "consultorio_id": consultorio_id,
        "paciente_id": paciente.id,
    }


async def insertar_historia_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    consultorio_id: uuid.UUID,
    paciente_id: uuid.UUID,
    abierta_por: uuid.UUID,
    historia_id: uuid.UUID | None = None,
) -> uuid.UUID:
    historia_id = historia_id or uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO historias_clinicas "
                "(id, consultorio_id, paciente_id, abierta_por) "
                "VALUES (:id, :consultorio_id, :paciente_id, :abierta_por)"
            ),
            {
                "id": historia_id,
                "consultorio_id": consultorio_id,
                "paciente_id": paciente_id,
                "abierta_por": abierta_por,
            },
        )
    return historia_id


async def insertar_evolucion_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    historia_id: uuid.UUID,
    profesional_id: uuid.UUID,
    creado_por: uuid.UUID,
    texto: str = "Evolución de prueba",
    firmada: bool = False,
    firmada_por: uuid.UUID | None = None,
    fecha_firma: datetime | None = None,
    rectifica_a: uuid.UUID | None = None,
    evolucion_id: uuid.UUID | None = None,
) -> uuid.UUID:
    evolucion_id = evolucion_id or uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO evoluciones "
                "(id, historia_id, profesional_id, creado_por, texto, "
                "firmada, firmada_por, fecha_firma, rectifica_a) "
                "VALUES (:id, :historia_id, :profesional_id, :creado_por, "
                ":texto, :firmada, :firmada_por, :fecha_firma, :rectifica_a)"
            ),
            {
                "id": evolucion_id,
                "historia_id": historia_id,
                "profesional_id": profesional_id,
                "creado_por": creado_por,
                "texto": texto,
                "firmada": firmada,
                "firmada_por": firmada_por,
                "fecha_firma": fecha_firma,
                "rectifica_a": rectifica_a,
            },
        )
    return evolucion_id


async def insertar_odontograma_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    historia_id: uuid.UUID,
    version: int,
    odontograma_id: uuid.UUID | None = None,
) -> uuid.UUID:
    odontograma_id = odontograma_id or uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO odontogramas (id, historia_id, version) "
                "VALUES (:id, :historia_id, :version)"
            ),
            {
                "id": odontograma_id,
                "historia_id": historia_id,
                "version": version,
            },
        )
    return odontograma_id


async def insertar_hallazgo_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    odontograma_id: uuid.UUID,
    pieza: int = 16,
    cara: str = "mesial",
    estado: str = "caries",
    diagnostico: str | None = None,
    cie10: str | None = "K02.1",
    fecha: date | None = None,
    hallazgo_id: uuid.UUID | None = None,
) -> uuid.UUID:
    hallazgo_id = hallazgo_id or uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO hallazgos_dentales "
                "(id, odontograma_id, pieza, cara, estado, diagnostico, "
                "cie10, fecha) "
                "VALUES (:id, :odontograma_id, :pieza, :cara, :estado, "
                ":diagnostico, :cie10, :fecha)"
            ),
            {
                "id": hallazgo_id,
                "odontograma_id": odontograma_id,
                "pieza": pieza,
                "cara": cara,
                "estado": estado,
                "diagnostico": diagnostico,
                "cie10": cie10,
                "fecha": fecha or date(2026, 11, 9),
            },
        )
    return hallazgo_id


async def insertar_consentimiento_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    consultorio_id: uuid.UUID,
    paciente_id: uuid.UUID,
    registrado_por: uuid.UUID,
    tipo: str = "procedimiento_invasivo",
    texto_version: str = "v1-2026-11",
    texto_hash: str = "a" * 64,
    firma_ref: str = "sha256:" + "b" * 64,
    fecha: datetime | None = None,
    consentimiento_id: uuid.UUID | None = None,
) -> uuid.UUID:
    consentimiento_id = consentimiento_id or uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO consentimientos "
                "(id, consultorio_id, paciente_id, tipo, texto_version, "
                "texto_hash, firma_ref, fecha, registrado_por) "
                "VALUES (:id, :consultorio_id, :paciente_id, :tipo, "
                ":texto_version, :texto_hash, :firma_ref, :fecha, "
                ":registrado_por)"
            ),
            {
                "id": consentimiento_id,
                "consultorio_id": consultorio_id,
                "paciente_id": paciente_id,
                "tipo": tipo,
                "texto_version": texto_version,
                "texto_hash": texto_hash,
                "firma_ref": firma_ref,
                "fecha": fecha or datetime.now(timezone.utc),
                "registrado_por": registrado_por,
            },
        )
    return consentimiento_id


async def auditorias(
    session_factory: async_sessionmaker[AsyncSession],
    accion: str | None = None,
) -> list[RegistroAuditoria]:
    """Audit rows, optionally filtered by action, oldest first."""
    statement = select(RegistroAuditoria).order_by(
        RegistroAuditoria.timestamp, RegistroAuditoria.id
    )
    if accion is not None:
        statement = statement.where(RegistroAuditoria.accion == accion)
    async with session_factory() as session:
        return list(await session.scalars(statement))
