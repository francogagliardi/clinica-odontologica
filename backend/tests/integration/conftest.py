"""Integration test bootstrap: real PostgreSQL, disposable schema.

Constraints, partial indexes, CHECKs and triggers do not exist in SQLite, so
these tests run against the Compose database. Set `TEST_DATABASE_URL` to a
**disposable** database: each test drops schema `public` first.

The schema is built by `alembic upgrade head`, never by `create_all`, so the
tests exercise the same DDL that ships to the environment (R-04).
"""

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from tests.integration.helpers import reset_schema, run

BACKEND_DIR = Path(__file__).resolve().parents[2]
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def require_database() -> str:
    """Skip loudly when no disposable database was provided."""
    if not TEST_DATABASE_URL:
        pytest.skip(
            "TEST_DATABASE_URL no está definida: los tests de integración "
            "requieren PostgreSQL real (R-04)."
        )
    return TEST_DATABASE_URL


@pytest.fixture
def database_url() -> str:
    return require_database()


@pytest.fixture
def migrated_database(database_url: str) -> str:
    """Clean schema + `alembic upgrade head` per test: isolated and honest."""
    run(reset_schema(database_url))
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        check=True,
        capture_output=True,
    )
    return database_url


@pytest.fixture
def engine(migrated_database: str) -> Iterator[AsyncEngine]:
    """Fresh engine per test: no pooled connections across event loops."""
    async_engine = create_async_engine(migrated_database, poolclass=NullPool)
    yield async_engine
    run(async_engine.dispose())


@pytest.fixture
def session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
