"""Engine and session factory helpers (R-04).

Kept separate from `app.core.resources` so scripts (seed, tests) can build
their own engine without the FastAPI lifespan.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str) -> AsyncEngine:
    """Async engine with connection checks before reuse."""
    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Session factory owned by whichever unit of work opens the session."""
    return async_sessionmaker(engine, expire_on_commit=False)
