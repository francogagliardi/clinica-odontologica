"""Alembic env regression guard (C-01 task 4.1 defect).

The canonical DATABASE_URL is an async driver URL
(`postgresql+asyncpg://`); env.py MUST therefore drive migrations through
the async engine path. The sync `engine_from_config` path raises
`sqlalchemy.exc.MissingGreenlet` against that URL. These tests guard the
contract without touching a live database (source-level seam only).
"""

from pathlib import Path

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


def test_single_head_revision_file() -> None:
    """versions/ holds exactly the single base head (no domain migrations)."""
    versions = sorted(
        p.name for p in (_BACKEND_DIR / "alembic" / "versions").glob("*.py")
    )
    assert versions == ["0001_base.py"]
