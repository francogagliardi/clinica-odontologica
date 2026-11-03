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
    """The revision graph has exactly one head (C-03 extends the chain)."""
    config = Config(str(_BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0003_tokens_un_solo_uso"]


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
