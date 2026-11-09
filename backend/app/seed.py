"""Idempotent demo seed (C-02/C-16).

Creates the five role names, the demo consultorio, the administrator and — when
`incluir_elenco` is on (the default and the CLI path) — the full demo cast:
odontólogo, recepción, asistente and auditor, the linked professional, two
chairs, the service catalogue, "OS Demo", three fictional patients and three
future appointments of the next business day.

`SEED_ADMIN_PASSWORD` and `SEED_DEMO_PASSWORD` are required and have no default
(R-08); a second run never rewrites a stored hash and never duplicates rows.
`pg_advisory_xact_lock` serializes concurrent seeds.

Usage:
    SEED_ADMIN_PASSWORD=<password> SEED_DEMO_PASSWORD=<password> \
        python -m app.seed
"""

import asyncio
import os
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import bcrypt
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import load_settings
from app.domain.agenda import ARGENTINA_OFFSET
from app.infrastructure.db import create_engine, create_session_factory
from app.models import (
    Consultorio,
    ObraSocial,
    Paciente,
    Prestacion,
    Profesional,
    ProfesionalSillon,
    Rol,
    Sillon,
    Turno,
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

# Full demo cast (D10). Emails use the reserved `.test` domain and all names
# carry "Demo": no real people, documents or contact data.
DEMO_USERS: tuple[dict[str, str], ...] = (
    {
        "email": "odonto.demo@clinica.test",
        "nombre": "Odontólogo Demo",
        "rol": "odontologo",
    },
    {
        "email": "recepcion.demo@clinica.test",
        "nombre": "Recepción Demo",
        "rol": "recepcionista",
    },
    {
        "email": "asistente.demo@clinica.test",
        "nombre": "Asistente Demo",
        "rol": "asistente",
    },
    {
        "email": "auditor.demo@clinica.test",
        "nombre": "Auditor Demo",
        "rol": "auditor",
    },
)

PROFESIONAL_MATRICULA = "MP-DEMO-1"
PROFESIONAL_ESPECIALIDADES = ["general", "endodoncia"]
PROFESIONAL_DURACION_BASE_MIN = 30
PROFESIONAL_DIAS_ATENCION = (0, 1, 2, 3, 4)
PROFESIONAL_HORA_DESDE = time(8, 0)
PROFESIONAL_HORA_HASTA = time(18, 0)

# Constant key for the transaction advisory lock that serializes concurrent
# seeds without a unique-index race (23505).
ADVISORY_LOCK_SEED = 160918

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

# Three appointments of the next business day (D10); created only when the
# consultorio has no appointments yet, so a re-run does not duplicate them.
TURNOS_DEMO: tuple[dict[str, object], ...] = (
    {"hora": 9, "estado": "reservado", "dni": "30111222"},
    {"hora": 10, "estado": "confirmado", "dni": "28999888"},
    {"hora": 11, "estado": "en_sala", "dni": "33444555"},
)
DURACION_TURNO_DEMO_MIN = 30


def hash_password(password: str) -> str:
    """Hash a password with bcrypt (never store plain text, R-03)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()


def proxima_jornada_habil(desde: date) -> date:
    """Next Monday–Friday strictly after `desde` (demo agenda never expires)."""
    dia = desde + timedelta(days=1)
    while dia.weekday() >= 5:
        dia += timedelta(days=1)
    return dia


async def run_seed(
    session: AsyncSession,
    admin_password: str,
    demo_password: str,
    *,
    incluir_elenco: bool = True,
) -> None:
    """Populate the demo data; safe to run many times and in parallel.

    `incluir_elenco=False` keeps the legacy minimal seed used by focused test
    fixtures (roles, consultorio, admin and catalogue), while the CLI and the
    production demo always create the full cast.
    """
    if not admin_password.strip():
        raise ValueError(
            "SEED_ADMIN_PASSWORD no puede estar vacía: no se genera una "
            "contraseña por defecto (R-08)."
        )
    if incluir_elenco and not demo_password.strip():
        raise ValueError(
            "SEED_DEMO_PASSWORD no puede estar vacía: el elenco demo no usa "
            "una contraseña por defecto (R-08)."
        )

    # Serialize concurrent seeds before any write: one completes, the other
    # waits and then finds every natural key already present.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:clave)"),
        {"clave": ADVISORY_LOCK_SEED},
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

    if not incluir_elenco:
        return

    rol_ids = {
        nombre: identificador
        for nombre, identificador in (
            await session.execute(
                select(Rol.nombre, Rol.id).where(Rol.deleted_at.is_(None))
            )
        ).all()
    }
    demo_ids: dict[str, uuid.UUID] = {}
    for usuario in DEMO_USERS:
        await session.execute(
            insert(Usuario)
            .values(
                id=uuid.uuid4(),
                nombre=usuario["nombre"],
                email=usuario["email"],
                hash_password=hash_password(demo_password),
            )
            .on_conflict_do_nothing(
                index_elements=["email"], index_where=_ACTIVO
            )
        )
        usuario_id = await session.scalar(
            select(Usuario.id).where(
                Usuario.email == usuario["email"],
                Usuario.deleted_at.is_(None),
            )
        )
        if usuario_id is None:  # pragma: no cover - defensive
            raise RuntimeError(
                f"El seed no pudo resolver el usuario {usuario['email']}"
            )
        demo_ids[usuario["rol"]] = usuario_id
        await session.execute(
            insert(UsuarioRol)
            .values(
                usuario_id=usuario_id,
                rol_id=rol_ids[usuario["rol"]],
            )
            .on_conflict_do_nothing(
                index_elements=["usuario_id", "rol_id"]
            )
        )

    await session.execute(
        insert(Profesional)
        .values(
            id=uuid.uuid4(),
            consultorio_id=consultorio_id,
            usuario_id=demo_ids["odontologo"],
            matricula=PROFESIONAL_MATRICULA,
            especialidades=PROFESIONAL_ESPECIALIDADES,
            duracion_base_min=PROFESIONAL_DURACION_BASE_MIN,
            dias_atencion=list(PROFESIONAL_DIAS_ATENCION),
            hora_desde=PROFESIONAL_HORA_DESDE,
            hora_hasta=PROFESIONAL_HORA_HASTA,
        )
        .on_conflict_do_nothing(
            index_elements=["consultorio_id", "matricula"],
            index_where=_ACTIVO,
        )
    )
    profesional_id = await session.scalar(
        select(Profesional.id).where(
            Profesional.consultorio_id == consultorio_id,
            Profesional.matricula == PROFESIONAL_MATRICULA,
            Profesional.deleted_at.is_(None),
        )
    )
    sillon_ids = [
        sillon_id
        for sillon_id in (
            await session.scalars(
                select(Sillon.id).where(
                    Sillon.consultorio_id == consultorio_id,
                    Sillon.deleted_at.is_(None),
                )
            )
        )
    ]
    if profesional_id is None or not sillon_ids:  # pragma: no cover
        raise RuntimeError(
            "El seed no pudo resolver el profesional o los sillones demo"
        )
    for sillon_id in sillon_ids:
        await session.execute(
            insert(ProfesionalSillon)
            .values(profesional_id=profesional_id, sillon_id=sillon_id)
            .on_conflict_do_nothing(
                index_elements=["profesional_id", "sillon_id"]
            )
        )

    turnos_existentes = await session.scalar(
        select(func.count()).select_from(Turno)
    )
    if int(turnos_existentes or 0) == 0:
        prestacion_id = await session.scalar(
            select(Prestacion.id).where(
                Prestacion.codigo == "CONS",
                Prestacion.deleted_at.is_(None),
            )
        )
        pacientes = {
            dni: paciente_id
            for dni, paciente_id in (
                await session.execute(
                    select(Paciente.dni, Paciente.id).where(
                        Paciente.consultorio_id == consultorio_id,
                        Paciente.deleted_at.is_(None),
                    )
                )
            ).all()
        }
        dia = proxima_jornada_habil(
            datetime.now(ARGENTINA_OFFSET).date()
        )
        for datos in TURNOS_DEMO:
            inicio = datetime.combine(
                dia, time(int(datos["hora"]), 0), tzinfo=ARGENTINA_OFFSET
            )
            session.add(
                Turno(
                    id=uuid.uuid4(),
                    consultorio_id=consultorio_id,
                    paciente_id=pacientes[str(datos["dni"])],
                    profesional_id=profesional_id,
                    sillon_id=sillon_ids[0],
                    prestacion_id=prestacion_id,
                    inicio=inicio,
                    fin=inicio
                    + timedelta(minutes=DURACION_TURNO_DEMO_MIN),
                    estado=str(datos["estado"]),
                    origen="recepcion",
                    es_sobreturno=False,
                    color_sobreturno=None,
                    sena_estado="no_requiere",
                )
            )
        await session.flush()


async def main() -> None:
    """CLI entrypoint: fail before touching the DB if a secret is missing."""
    admin_password = os.environ.get("SEED_ADMIN_PASSWORD", "")
    demo_password = os.environ.get("SEED_DEMO_PASSWORD", "")
    faltantes = [
        nombre
        for nombre, valor in (
            ("SEED_ADMIN_PASSWORD", admin_password),
            ("SEED_DEMO_PASSWORD", demo_password),
        )
        if not valor.strip()
    ]
    if faltantes:
        raise RuntimeError(
            "Missing required environment variable(s): "
            f"{', '.join(faltantes)}. El seed abortó sin crear ningún registro."
        )

    settings = load_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            async with session.begin():
                await run_seed(session, admin_password, demo_password)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
