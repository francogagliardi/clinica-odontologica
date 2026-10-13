"""Reserved Redis queue-name contract (platform/job-queues).

Centralized constants only — no stub workers in C-01 by design (consumers
arrive in C-09/C-13/C-14). Exactly these three names may exist here (R-06:
Redis is queues/jobs only, never source of truth).
"""

import asyncio

import redis.asyncio as redis_async

WHATSAPP_SEND: str = "whatsapp:send"
RECORDATORIOS_DUE: str = "recordatorios:due"
ARCA_EMITIR: str = "arca:emitir"

ALL_QUEUES: tuple[str, ...] = (WHATSAPP_SEND, RECORDATORIOS_DUE, ARCA_EMITIR)

_ENQUEUE_TIMEOUT_SECONDS: float = 2.0


def get_redis_client(redis_url: str) -> redis_async.Redis:
    """Create a lazy Redis client configured by REDIS_URL (no I/O on build)."""
    return redis_async.from_url(
        redis_url,
        socket_connect_timeout=_ENQUEUE_TIMEOUT_SECONDS,
        socket_timeout=_ENQUEUE_TIMEOUT_SECONDS,
        decode_responses=True,
    )


async def try_enqueue(client: redis_async.Redis, queue: str, payload: str) -> bool:
    """Best-effort non-blocking enqueue.

    Never raises on Redis outage: the caller keeps its primary response and
    the failure is signalled for future retry instead of breaking the request.
    """
    if queue not in ALL_QUEUES:
        raise ValueError(f"Unknown queue: {queue}")
    try:
        await asyncio.wait_for(
            client.rpush(queue, payload), timeout=_ENQUEUE_TIMEOUT_SECONDS
        )
    except Exception:
        return False
    return True
