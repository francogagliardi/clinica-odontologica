"""Shared helpers for integration tests (no pytest import needed)."""

import asyncio
from typing import Awaitable, TypeVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

T = TypeVar("T")


def run(coro: Awaitable[T]) -> T:
    """Run one coroutine in its own event loop (no pytest-asyncio dependency)."""
    return asyncio.run(coro)


async def reset_schema(database_url: str) -> None:
    """Drop and recreate `public`: a genuinely empty database for the test."""
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
    finally:
        await engine.dispose()


def sqlstate(error: BaseException) -> str | None:
    """Extract the PostgreSQL SQLSTATE from a SQLAlchemy/DBAPI exception."""
    original = getattr(error, "orig", error)
    return getattr(original, "sqlstate", None) or getattr(
        original, "pgcode", None
    )
