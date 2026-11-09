"""Full demo seed: exact counts, logins, secrets, idempotency and concurrency.

C-16 task 9.1. Every test starts from a freshly migrated, empty schema managed
by the `session_factory` fixture, so counts are exact and independent.
"""

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

import app.seed as seed_module
from app.domain.agenda import ARGENTINA_OFFSET
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
from app.seed import (
    ADMIN_EMAIL,
    DEMO_USERS,
    PROFESIONAL_MATRICULA,
    PACIENTES_DEMO,
    PRESTACIONES_DEMO,
    ROLES,
    SILLONES_DEMO,
    main,
    run_seed,
)
from tests.integration.helpers import run

ADMIN_PW = "admin-demo-pass-2026"
DEMO_PW = "staff-demo-pass-2026"


async def _seed(
    session_factory,
    admin_password: str = ADMIN_PW,
    demo_password: str = DEMO_PW,
) -> None:
    async with session_factory() as session, session.begin():
        await run_seed(session, admin_password, demo_password)


async def _count(session_factory, model) -> int:
    async with session_factory() as session:
        return int(
            await session.scalar(select(func.count()).select_from(model)) or 0
        )


async def _conteos(session_factory) -> dict[str, int]:
    return {
        "roles": await _count(session_factory, Rol),
        "consultorios": await _count(session_factory, Consultorio),
        "usuarios": await _count(session_factory, Usuario),
        "usuario_roles": await _count(session_factory, UsuarioRol),
        "profesionales": await _count(session_factory, Profesional),
        "sillones": await _count(session_factory, Sillon),
        "prestaciones": await _count(session_factory, Prestacion),
        "obras_sociales": await _count(session_factory, ObraSocial),
        "pacientes": await _count(session_factory, Paciente),
        "turnos": await _count(session_factory, Turno),
        "profesional_sillones": await _count(
            session_factory, ProfesionalSillon
        ),
    }


def _conteos_esperados() -> dict[str, int]:
    return {
        "roles": len(ROLES),
        "consultorios": 1,
        "usuarios": 1 + len(DEMO_USERS),
        "usuario_roles": 1 + len(DEMO_USERS),
        "profesionales": 1,
        "sillones": len(SILLONES_DEMO),
        "prestaciones": len(PRESTACIONES_DEMO),
        "obras_sociales": 1,
        "pacientes": len(PACIENTES_DEMO),
        "turnos": 3,
        "profesional_sillones": len(SILLONES_DEMO),
    }


def test_primera_corrida_conteos_exactos(session_factory) -> None:
    """Expected: the full demo cast and agenda exist exactly once."""

    async def scenario() -> None:
        await _seed(session_factory)
        assert await _conteos(session_factory) == _conteos_esperados()

        async with session_factory() as session:
            emails = set(
                await session.scalars(select(Usuario.email))
            )
            assert emails == {
                ADMIN_EMAIL,
                *(usuario["email"] for usuario in DEMO_USERS),
            }

            odontologo = await session.scalar(
                select(Usuario).where(
                    Usuario.email == "odonto.demo@clinica.test"
                )
            )
            assert odontologo is not None
            profesional = await session.scalar(
                select(Profesional).where(
                    Profesional.matricula == PROFESIONAL_MATRICULA
                )
            )
            assert profesional is not None
            assert profesional.usuario_id == odontologo.id

    run(scenario())


def test_login_de_los_cinco_roles(api_client, session_factory) -> None:
    """Expected: every seeded user authenticates with its demo password."""

    run(_seed(session_factory))
    credenciales = [
        (ADMIN_EMAIL, ADMIN_PW, "administrador"),
        (
            "odonto.demo@clinica.test",
            DEMO_PW,
            "odontologo",
        ),
        (
            "recepcion.demo@clinica.test",
            DEMO_PW,
            "recepcionista",
        ),
        (
            "asistente.demo@clinica.test",
            DEMO_PW,
            "asistente",
        ),
        (
            "auditor.demo@clinica.test",
            DEMO_PW,
            "auditor",
        ),
    ]
    for email, password, rol in credenciales:
        response = api_client.post(
            "/usuarios/login", json={"email": email, "password": password}
        )
        assert response.status_code == 200, (email, response.text)
        assert response.json()["usuario"]["roles"] == [rol]


def test_sin_password_admin_aborta_sin_escribir(session_factory) -> None:
    """Business error: the admin secret is mandatory and named."""

    async def scenario() -> None:
        with pytest.raises(ValueError, match="SEED_ADMIN_PASSWORD"):
            await _seed(session_factory, admin_password="   ")
        assert await _conteos(session_factory) == {
            clave: 0 for clave in _conteos_esperados()
        }

    run(scenario())


def test_sin_password_demo_aborta_sin_escribir(session_factory) -> None:
    """Business error: the demo cast secret is mandatory and named."""

    async def scenario() -> None:
        with pytest.raises(ValueError, match="SEED_DEMO_PASSWORD"):
            await _seed(session_factory, demo_password="")
        assert await _conteos(session_factory) == {
            clave: 0 for clave in _conteos_esperados()
        }

    run(scenario())


def test_cli_nombra_la_variable_faltante(monkeypatch) -> None:
    """Edge: the CLI validates both secrets before opening a connection."""

    monkeypatch.delenv("SEED_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("SEED_DEMO_PASSWORD", DEMO_PW)
    with pytest.raises(RuntimeError, match="SEED_ADMIN_PASSWORD"):
        asyncio.run(main())

    monkeypatch.setenv("SEED_ADMIN_PASSWORD", ADMIN_PW)
    monkeypatch.delenv("SEED_DEMO_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="SEED_DEMO_PASSWORD"):
        asyncio.run(main())


def test_segunda_corrida_es_identica(session_factory) -> None:
    """Edge: re-running duplicates nothing and keeps every count."""

    async def scenario() -> None:
        await _seed(session_factory)
        primero = await _conteos(session_factory)
        await _seed(session_factory)
        assert await _conteos(session_factory) == primero

    run(scenario())


def test_otra_password_no_reescribe_credenciales(session_factory) -> None:
    """Business rule: a second seed never rotates stored hashes."""

    async def scenario() -> None:
        await _seed(session_factory, "primera-admin", "primera-demo")
        async with session_factory() as session:
            originales = dict(
                (
                    await session.execute(
                        select(Usuario.email, Usuario.hash_password)
                    )
                ).all()
            )

        await _seed(session_factory, "segunda-admin", "segunda-demo")
        async with session_factory() as session:
            actuales = dict(
                (
                    await session.execute(
                        select(Usuario.email, Usuario.hash_password)
                    )
                ).all()
            )
        assert actuales == originales

    run(scenario())


def test_dos_seeds_concurrentes_no_fallan(session_factory) -> None:
    """Edge: the advisory lock serializes both seeds without a 23505."""

    async def scenario() -> None:
        await asyncio.gather(
            _seed(session_factory),
            _seed(session_factory),
        )
        assert await _conteos(session_factory) == _conteos_esperados()

    run(scenario())


def test_base_parcial_se_completa_sin_duplicar(session_factory) -> None:
    """Edge: pre-existing demo rows are respected and only missing ones added."""

    async def scenario() -> None:
        async with session_factory() as session, session.begin():
            session.add(Rol(nombre="administrador"))
            consultorio = Consultorio(
                nombre="Consultorio Pre-existente",
                slug="demo",
            )
            session.add(consultorio)
            await session.flush()
            session.add(
                Paciente(
                    consultorio_id=consultorio.id,
                    nombre="Ana",
                    apellido="Previa",
                    dni=PACIENTES_DEMO[0]["dni"],
                    telefono=PACIENTES_DEMO[0]["telefono"],
                )
            )
            session.add(
                Prestacion(
                    codigo="CONS",
                    nombre="Consulta Pre-existente",
                    duracion_min=30,
                    precio_base=PRESTACIONES_DEMO[0]["precio_base"],
                    especialidad="general",
                )
            )

        await _seed(session_factory)
        assert await _conteos(session_factory) == _conteos_esperados()
        async with session_factory() as session:
            consultorio = await session.scalar(
                select(Consultorio).where(Consultorio.slug == "demo")
            )
            assert consultorio is not None
            assert consultorio.nombre == "Consultorio Pre-existente"
            ana = await session.scalar(
                select(Paciente).where(
                    Paciente.dni == PACIENTES_DEMO[0]["dni"]
                )
            )
            assert ana is not None and ana.apellido == "Previa"

    run(scenario())


def test_turnos_futuros_sin_solape(session_factory) -> None:
    """Expected: three future business-day appointments, one per patient."""

    async def scenario() -> None:
        await _seed(session_factory)
        async with session_factory() as session:
            turnos = list(await session.scalars(select(Turno)))
            ahora = datetime.now(timezone.utc)

            assert len(turnos) == 3
            assert {turno.estado for turno in turnos} == {
                "reservado",
                "confirmado",
                "en_sala",
            }
            assert len({turno.paciente_id for turno in turnos}) == 3
            assert len({turno.profesional_id for turno in turnos}) == 1
            assert len({turno.sillon_id for turno in turnos}) == 1
            for turno in turnos:
                assert turno.inicio > ahora
                assert turno.inicio.astimezone(ARGENTINA_OFFSET).weekday() < 5
                assert (
                    turno.fin - turno.inicio
                ).total_seconds() == 30 * 60
            ordenados = sorted(turnos, key=lambda turno: turno.inicio)
            for anterior, siguiente in zip(ordenados, ordenados[1:]):
                assert anterior.fin <= siguiente.inicio
            assert sorted(
                turno.inicio.astimezone(ARGENTINA_OFFSET).hour
                for turno in turnos
            ) == [9, 10, 11]

    run(scenario())


def test_datos_ficticios_sin_pii_real(session_factory) -> None:
    """Business rule: `.test` domains and Demo names only."""

    async def scenario() -> None:
        await _seed(session_factory)
        async with session_factory() as session:
            emails = list(await session.scalars(select(Usuario.email)))
            assert all(email.endswith(".test") for email in emails)
            pacientes = list(await session.scalars(select(Paciente)))
            assert all(paciente.apellido == "Demo" for paciente in pacientes)
            assert all(
                paciente.email is None
                or paciente.email.endswith(".test")
                for paciente in pacientes
            )
            assert all(
                paciente.telefono.startswith("+549")
                for paciente in pacientes
            )

    run(scenario())


def test_las_constantes_del_seed_son_las_esperadas() -> None:
    """Guard: the demo cast and passwords are read from the environment only."""

    assert ADMIN_EMAIL == "admin@clinica.test"
    assert {usuario["rol"] for usuario in DEMO_USERS} == {
        "odontologo",
        "recepcionista",
        "asistente",
        "auditor",
    }
    assert PROFESIONAL_MATRICULA == "MP-DEMO-1"
    assert seed_module.ADVISORY_LOCK_SEED
