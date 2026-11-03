"""Idempotent demo seed for C-02.

Creates the five role names, one demo consultorio and one demo administrator.
`SEED_ADMIN_PASSWORD` is required and has no default (R-08); re-running never
rewrites an existing password hash and never duplicates rows.

Usage:
    SEED_ADMIN_PASSWORD=<password> python -m app.seed
"""

import asyncio
import os
import uuid
from decimal import Decimal

import bcrypt
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import load_settings
from app.infrastructure.db import create_engine, create_session_factory
from app.models import (
    Consultorio,
    ObraSocial,
    Paciente,
    Prestacion,
    Rol,
    Sillon,
    Usuario,
    UsuarioRol,
)

ROLES: tuple[str, ...] = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)
CONSULTORIO_DEMO_SLUG = "demo"
CONSULTORIO_DEMO_NOMBRE = "Consultorio Demo"
ADMIN_EMAIL = "admin@clinica.test"
ADMIN_NOMBRE = "Administrador Demo"

# Fictional demo catalogue (04_modelo_de_datos.md §Seed). ENDO exercises
# RN-TU-08 without ever charging a real deposit (R-12).
SILLONES_DEMO: tuple[str, ...] = ("Sillón 1", "Sillón 2")
PRESTACIONES_DEMO: tuple[dict[str, object], ...] = (
    {
        "codigo": "CONS",
        "nombre": "Consulta odontológica",
        "duracion_min": 30,
        "precio_base": Decimal("12000.00"),
        "especialidad": "general",
    },
    {
        "codigo": "LIM",
        "nombre": "Limpieza dental",
        "duracion_min": 45,
        "precio_base": Decimal("18000.00"),
        "especialidad": "general",
    },
    {
        "codigo": "OBT",
        "nombre": "Obturación",
        "duracion_min": 60,
        "precio_base": Decimal("25000.00"),
        "especialidad": "general",
    },
    {
        "codigo": "ENDO",
        "nombre": "Endodoncia",
        "duracion_min": 90,
        "precio_base": Decimal("60000.00"),
        "especialidad": "endodoncia",
        "requiere_sena": True,
        "monto_sena": Decimal("10000.00"),
    },
    {
        "codigo": "EXO",
        "nombre": "Extracción",
        "duracion_min": 60,
        "precio_base": Decimal("30000.00"),
        "especialidad": "cirugia",
    },
)

# Partial unique indexes only cover active rows; ON CONFLICT must be told so.
_ACTIVO = text("deleted_at IS NULL")

# Fictional agreement (DD-11): local rules only, never a real payer (R-12).
OBRA_SOCIAL_DEMO: dict[str, object] = {
    "nombre": "OS Demo",
    "nomenclador_ref": "DEMO-LOCAL",
    "reglas_cobertura": {
        "cobertura_porcentaje": 60,
        "copago_porcentaje": 40,
        "prestaciones_cubiertas": ["CONS", "LIM", "OBT"],
        "requiere_autorizacion": False,
    },
    "validacion_externa": False,
}

# Fictional patients for the demo; never real people or real documents.
PACIENTES_DEMO: tuple[dict[str, object], ...] = (
    {
        "nombre": "Ana",
        "apellido": "Demo",
        "dni": "30111222",
        "telefono": "+5491145550001",
        "email": "ana.demo@example.test",
        "con_cobertura": True,
        "nro_afiliado": "DEMO-0001",
    },
    {
        "nombre": "Bruno",
        "apellido": "Demo",
        "dni": "28999888",
        "telefono": "+5491145550002",
        "email": "bruno.demo@example.test",
        "con_cobertura": True,
        "nro_afiliado": "DEMO-0002",
    },
    {
        "nombre": "Carla",
        "apellido": "Demo",
        "dni": "33444555",
        "telefono": "+5491145550003",
        "email": "carla.demo@example.test",
        "con_cobertura": False,
        "nro_afiliado": None,
    },
)


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (never store plain text, R-03)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()


async def run_seed(session: AsyncSession, admin_password: str) -> None:
    """Populate the minimum demo data; safe to run many times and in parallel."""
    if not admin_password.strip():
        raise ValueError(
            "SEED_ADMIN_PASSWORD no puede estar vacía: no se genera una "
            "contraseña por defecto (R-08)."
        )

    for nombre in ROLES:
        await session.execute(
            insert(Rol)
            .values(id=uuid.uuid4(), nombre=nombre)
            .on_conflict_do_nothing(
                index_elements=["nombre"], index_where=_ACTIVO
            )
        )

    await session.execute(
        insert(Consultorio)
        .values(
            id=uuid.uuid4(),
            slug=CONSULTORIO_DEMO_SLUG,
            nombre=CONSULTORIO_DEMO_NOMBRE,
        )
        .on_conflict_do_nothing(index_elements=["slug"], index_where=_ACTIVO)
    )

    consultorio_id = await session.scalar(
        select(Consultorio.id).where(
            Consultorio.slug == CONSULTORIO_DEMO_SLUG,
            Consultorio.deleted_at.is_(None),
        )
    )
    if consultorio_id is None:  # pragma: no cover - defensive
        raise RuntimeError(
            "El seed no pudo resolver el consultorio demo; "
            "revisar las restricciones de unicidad."
        )

    for nombre in SILLONES_DEMO:
        await session.execute(
            insert(Sillon)
            .values(
                id=uuid.uuid4(),
                consultorio_id=consultorio_id,
                nombre=nombre,
            )
            .on_conflict_do_nothing(
                index_elements=["consultorio_id", "nombre"],
                index_where=_ACTIVO,
            )
        )

    for datos in PRESTACIONES_DEMO:
        await session.execute(
            insert(Prestacion)
            .values(id=uuid.uuid4(), **datos)
            .on_conflict_do_nothing(
                index_elements=["codigo"], index_where=_ACTIVO
            )
        )

    # The target-less ON CONFLICT also covers expression indexes (lower(nombre)).
    await session.execute(
        insert(ObraSocial)
        .values(
            id=uuid.uuid4(),
            consultorio_id=consultorio_id,
            **OBRA_SOCIAL_DEMO,
        )
        .on_conflict_do_nothing()
    )
    obra_social_id = await session.scalar(
        select(ObraSocial.id).where(
            func.lower(ObraSocial.nombre)
            == OBRA_SOCIAL_DEMO["nombre"].lower(),
            ObraSocial.deleted_at.is_(None),
        )
    )

    for datos in PACIENTES_DEMO:
        valores = {
            clave: valor
            for clave, valor in datos.items()
            if clave != "con_cobertura"
        }
        await session.execute(
            insert(Paciente)
            .values(
                id=uuid.uuid4(),
                consultorio_id=consultorio_id,
                obra_social_id=(
                    obra_social_id if datos["con_cobertura"] else None
                ),
                **valores,
            )
            .on_conflict_do_nothing()
        )

    # The hash is computed for the insert attempt only: if the row already
    # exists the conflict is ignored, so a re-run never changes credentials.
    await session.execute(
        insert(Usuario)
        .values(
            id=uuid.uuid4(),
            nombre=ADMIN_NOMBRE,
            email=ADMIN_EMAIL,
            hash_password=hash_password(admin_password),
        )
        .on_conflict_do_nothing(index_elements=["email"], index_where=_ACTIVO)
    )

    admin_id = await session.scalar(
        select(Usuario.id).where(
            Usuario.email == ADMIN_EMAIL, Usuario.deleted_at.is_(None)
        )
    )
    rol_admin_id = await session.scalar(
        select(Rol.id).where(
            Rol.nombre == "administrador", Rol.deleted_at.is_(None)
        )
    )
    if admin_id is None or rol_admin_id is None:  # pragma: no cover - defensive
        raise RuntimeError(
            "El seed no pudo resolver el administrador o su rol; "
            "revisar las restricciones de unicidad."
        )

    await session.execute(
        insert(UsuarioRol)
        .values(usuario_id=admin_id, rol_id=rol_admin_id)
        .on_conflict_do_nothing(index_elements=["usuario_id", "rol_id"])
    )


async def main() -> None:
    """CLI entrypoint: fail before touching the DB if the secret is missing."""
    admin_password = os.environ.get("SEED_ADMIN_PASSWORD", "")
    if not admin_password.strip():
        raise RuntimeError(
            "Missing required environment variable(s): SEED_ADMIN_PASSWORD. "
            "El seed abortó sin crear ningún registro."
        )

    settings = load_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            async with session.begin():
                await run_seed(session, admin_password)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
