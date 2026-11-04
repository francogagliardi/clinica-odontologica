"""Alembic env regression guard (C-01 task 4.1 defect).

The canonical DATABASE_URL is an async driver URL
(`postgresql+asyncpg://`); env.py MUST therefore drive migrations through
the async engine path. The sync `engine_from_config` path raises
`sqlalchemy.exc.MissingGreenlet` against that URL. These tests guard the
contract without touching a live database (source-level seam only).
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ENV_SOURCE = (_BACKEND_DIR / "alembic" / "env.py").read_text(encoding="utf-8")
_BASE_SOURCE = (
    _BACKEND_DIR / "alembic" / "versions" / "0001_base.py"
).read_text(encoding="utf-8")


def test_env_uses_async_engine_path() -> None:
    """env.py drives online migrations via the async engine + run_sync."""
    assert "async_engine_from_config" in _ENV_SOURCE
    assert "run_sync" in _ENV_SOURCE
    assert "engine_from_config(" not in _ENV_SOURCE.replace(
        "async_engine_from_config(", ""
    )


def test_baseline_revision_carries_zero_domain_ddl() -> None:
    """0001_base stays an empty head marker (no domain CREATE TABLE)."""
    lowered = _BASE_SOURCE.lower()
    assert "create_table" not in lowered
    assert "create_index" not in lowered
    assert 'revision: str = "0001_base"' in _BASE_SOURCE


def test_single_head_revision() -> None:
    """The revision graph has exactly one head (C-12 extends the chain)."""
    config = Config(str(_BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0011_presupuestos"]


def test_c02_revision_chains_from_baseline() -> None:
    """0002 declares its dependency instead of branching the history."""
    source = (
        _BACKEND_DIR / "alembic" / "versions" / "0002_core_models_seguridad.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0001_base"' in source


def test_c03_revision_chains_from_c02() -> None:
    """0003 adds the public tokens table on top of the C-02 schema."""
    source = (
        _BACKEND_DIR / "alembic" / "versions" / "0003_tokens_un_solo_uso.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0002_core_models_seguridad"' in source
    assert "tokens_un_solo_uso" in source


def test_c04_revision_chains_from_c03() -> None:
    """0004 adds agenda resources and the service catalogue."""
    source = (
        _BACKEND_DIR / "alembic" / "versions" / "0004_recursos_agendables.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0003_tokens_un_solo_uso"' in source
    assert "profesionales" in source
    assert "prestaciones" in source
    assert "bloqueos" in source


def test_c05_revision_chains_from_c04() -> None:
    """0005 adds patients and social-security agreements on top of C-04."""
    source = (
        _BACKEND_DIR / "alembic" / "versions" / "0005_pacientes_cobertura_base.py"
    ).read_text(encoding="utf-8")
    assert (
        'down_revision: str | None = "0004_recursos_agendables"' in source
    )
    assert "pacientes" in source
    assert "obras_sociales" in source


def test_c06_revision_chains_from_c05() -> None:
    """0006 adds appointments, the anti-overlap constraints and cancellation."""
    source = (
        _BACKEND_DIR / "alembic" / "versions" / "0006_turnos_anti_solapamiento.py"
    ).read_text(encoding="utf-8")
    assert (
        'down_revision: str | None = "0005_pacientes_cobertura_base"' in source
    )
    assert "btree_gist" in source
    assert "ex_turnos_profesional" in source
    assert "ex_turnos_sillon" in source
    assert "plazo_cancelacion_horas" in source


def test_c07_revision_chains_from_c06() -> None:
    """0007 adds the deposit state used by the public booking flow."""
    source = (
        _BACKEND_DIR / "alembic" / "versions" / "0007_reserva_publica.py"
    ).read_text(encoding="utf-8")
    assert (
        'down_revision: str | None = "0006_turnos_anti_solapamiento"' in source
    )
    assert "sena_estado" in source


def test_c08_revision_chains_from_c07() -> None:
    """0008 adds reminders and WhatsApp messages on top of the public booking."""
    source = (
        _BACKEND_DIR / "alembic" / "versions" / "0008_whatsapp_recordatorios.py"
    ).read_text(encoding="utf-8")
    assert (
        'down_revision: str | None = "0007_reserva_publica"' in source
    )
    assert "recordatorios" in source
    assert "mensajes_whatsapp" in source


def test_c10_revision_chains_from_c08() -> None:
    """0009 adds the waiting list and its retention constraints."""
    source = (
        _BACKEND_DIR / "alembic" / "versions" / "0009_lista_espera.py"
    ).read_text(encoding="utf-8")
    assert (
        'down_revision: str | None = "0008_whatsapp_recordatorios"' in source
    )
    assert "entradas_lista_espera" in source
    assert "ex_lista_espera_profesional" in source
    assert "ex_lista_espera_sillon" in source
    assert "lista_espera_id" in source
    assert "btree_gist" in source


def test_c11_revision_chains_from_c10() -> None:
    """0010 adds the clinical record without branching the revision graph."""
    source = (
        _BACKEND_DIR / "alembic" / "versions" / "0010_historia_clinica.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0009_lista_espera"' in source
    assert "historias_clinicas" in source
    assert "evoluciones" in source
    assert "odontogramas" in source
    assert "hallazgos_dentales" in source
    assert "adjuntos" in source
    assert "consentimientos" in source
    assert "P0001" in source


def test_c12_revision_chains_from_c11() -> None:
    """0011 adds budgets and their lines on top of the clinical record."""
    source = (
        _BACKEND_DIR / "alembic" / "versions" / "0011_presupuestos.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0010_historia_clinica"' in source
    assert "presupuestos" in source
    assert "items_presupuesto" in source
    assert "subtotal = cobertura_calculada + copago" in source
    assert "pieza / 10 BETWEEN 1 AND 4" in source
