"""Builders for patient and insurance integration tests (fictional data only)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import ObraSocial, Paciente


def paciente_payload(
    dni: str = "40.111.222",
    telefono: str = "11 4444-5555",
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "nombre": "Ana",
        "apellido": "Gonzalez",
        "dni": dni,
        "telefono": telefono,
        "fecha_nacimiento": "1990-05-20",
        "email": "ana.demo@example.test",
        "obra_social_id": None,
        "nro_afiliado": None,
        "notas": "Paciente ficticio de prueba",
    }
    payload.update(overrides)
    return payload


def obra_social_payload(nombre: str = "OS Test") -> dict[str, object]:
    return {
        "nombre": nombre,
        "nomenclador_ref": "NOM-TEST",
        "reglas_cobertura": {
            "cobertura_porcentaje": 60,
            "copago_porcentaje": 40,
            "prestaciones_cubiertas": ["CONS", "LIM"],
            "requiere_autorizacion": False,
        },
        "validacion_externa": False,
    }


async def create_obra_social(
    session_factory: async_sessionmaker[AsyncSession],
    consultorio_id: uuid.UUID,
    nombre: str = "OS Test",
) -> ObraSocial:
    async with session_factory() as session, session.begin():
        obra_social = ObraSocial(
            id=uuid.uuid4(),
            consultorio_id=consultorio_id,
            nombre=nombre,
            nomenclador_ref="NOM-TEST",
            reglas_cobertura={"cobertura_porcentaje": 60},
        )
        session.add(obra_social)
    return obra_social


async def create_paciente(
    session_factory: async_sessionmaker[AsyncSession],
    consultorio_id: uuid.UUID,
    *,
    nombre: str,
    apellido: str,
    dni: str,
    telefono: str,
    obra_social_id: uuid.UUID | None = None,
    nro_afiliado: str | None = None,
) -> Paciente:
    async with session_factory() as session, session.begin():
        paciente = Paciente(
            id=uuid.uuid4(),
            consultorio_id=consultorio_id,
            nombre=nombre,
            apellido=apellido,
            dni=dni,
            telefono=telefono,
            obra_social_id=obra_social_id,
            nro_afiliado=nro_afiliado,
        )
        session.add(paciente)
    return paciente
