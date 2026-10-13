"""Process-wide shared resources, owned by the lifespan in app.main.

Engine/client construction is lazy (no I/O); probes in app.api.ready read
this module's state, so routers never import the app object (no cycles).
"""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.queues import get_redis_client
from app.core.settings import Settings

import redis.asyncio as redis_async

engine: AsyncEngine | None = None
redis_client: redis_async.Redis | None = None


def init_resources(settings: Settings) -> None:
    """Create the SQLAlchemy pool and the Redis client (lazy, no I/O)."""
    global engine, redis_client
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    redis_client = get_redis_client(settings.redis_url)


async def close_resources() -> None:
    """Dispose the pool and close Redis (lifespan shutdown)."""
    global engine, redis_client
    if engine is not None:
        await engine.dispose()
        engine = None
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None
