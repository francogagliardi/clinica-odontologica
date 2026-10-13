"""Readiness probe: 200 when backends are reachable, else 503 naming the failure."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.api.deps import reject_unexpected_query
from app.core import resources
from app.schemas.system import ReadinessResponse

router = APIRouter(tags=["system"])

_PROBE_TIMEOUT_SECONDS: float = 2.0


async def probe_database() -> str:
    """Return 'up' after SELECT 1, else 'down' (short timeout, no hangs)."""
    if resources.engine is None:
        return "down"
    try:
        async with resources.engine.connect() as connection:
            await asyncio.wait_for(
                connection.execute(text("SELECT 1")),
                timeout=_PROBE_TIMEOUT_SECONDS,
            )
    except Exception:
        return "down"
    return "up"


async def probe_redis() -> str:
    """Return 'up' after PING, else 'down' (short timeout, no hangs)."""
    if resources.redis_client is None:
        return "down"
    try:
        await asyncio.wait_for(
            resources.redis_client.ping(), timeout=_PROBE_TIMEOUT_SECONDS
        )
    except Exception:
        return "down"
    return "up"


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe (PostgreSQL + Redis)",
    dependencies=[Depends(reject_unexpected_query)],
)
async def get_readiness() -> ReadinessResponse:
    """Reflect dependency health; 503 detail identifies which one is down."""
    db_state, redis_state = await asyncio.gather(probe_database(), probe_redis())
    if db_state != "up" or redis_state != "up":
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "checks": {"db": db_state, "redis": redis_state},
            },
        )
    return ReadinessResponse(
        status="ready", checks={"db": db_state, "redis": redis_state}
    )
