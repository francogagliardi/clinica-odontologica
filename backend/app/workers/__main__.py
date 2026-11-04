"""Worker entrypoints: reminders scheduler and WhatsApp sender (C-09).

Usage:
    python -m app.workers recordatorios
    python -m app.workers whatsapp
"""

import asyncio
import sys
import uuid

import redis.asyncio as redis_async

from app.application.lista_espera import procesar_ofertas_vencidas
from app.application.recordatorios import (
    procesar_entrante,
    procesar_reintentos,
    procesar_vencidos,
)
from app.core.queues import WHATSAPP_SEND, get_redis_client
from app.core.settings import Settings, load_settings
from app.infrastructure.db import create_engine, create_session_factory
from app.infrastructure.uow import UnitOfWork
from app.infrastructure.whatsapp import get_whatsapp_client

_MODOS = ("recordatorios", "whatsapp")


async def run_once_recordatorios(settings: Settings) -> int:
    """Process all due reminders once (testable, no infinite loop)."""
    engine = create_engine(settings.database_url)
    client = get_redis_client(settings.redis_url)
    factory = create_session_factory(engine)
    try:
        async with UnitOfWork(factory) as uow:
            recordatorios = await procesar_vencidos(
                uow,
                client,
                base_url=settings.app_base_url,
                token_ttl_minutes=settings.gestion_token_ttl_minutes,
            )
            # The same tick expires due waiting-list offers and rotates them.
            ofertas = await procesar_ofertas_vencidas(
                uow,
                client,
                base_url=settings.app_base_url,
                ttl_minutos=settings.lista_espera_oferta_ttl_minutos,
            )
            return recordatorios + ofertas
    finally:
        await client.aclose()
        await engine.dispose()


async def run_once_whatsapp(
    settings: Settings, *, timeout: int = 1
) -> int | None:
    """Pop one queued message (or retry due ones) and process it."""
    engine = create_engine(settings.database_url)
    redis_client: redis_async.Redis = get_redis_client(settings.redis_url)
    cliente = get_whatsapp_client(settings)
    factory = create_session_factory(engine)
    try:
        item = await redis_client.brpop(WHATSAPP_SEND, timeout=timeout)
        async with UnitOfWork(factory) as uow:
            if item is not None:
                _, raw_id = item
                await procesar_entrante(
                    uow,
                    cliente,
                    uuid.UUID(raw_id),
                    max_intentos=settings.whatsapp_max_intentos,
                )
                return 1
            return await procesar_reintentos(
                uow,
                cliente,
                max_intentos=settings.whatsapp_max_intentos,
            )
    finally:
        await redis_client.aclose()
        await engine.dispose()


async def loop_recordatorios(settings: Settings) -> None:  # pragma: no cover
    while True:
        await run_once_recordatorios(settings)
        await asyncio.sleep(settings.whatsapp_worker_interval_seconds)


async def loop_whatsapp(settings: Settings) -> None:  # pragma: no cover
    while True:
        await run_once_whatsapp(settings)
        await asyncio.sleep(1)


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    modo = args[0] if args else ""
    if modo not in _MODOS:
        raise SystemExit(
            "Uso: python -m app.workers [recordatorios|whatsapp] [--once]"
        )
    settings = load_settings()
    if "--once" in args:
        if modo == "recordatorios":
            asyncio.run(run_once_recordatorios(settings))
        else:
            asyncio.run(run_once_whatsapp(settings, timeout=1))
        return
    loop = loop_recordatorios if modo == "recordatorios" else loop_whatsapp
    asyncio.run(loop(settings))


if __name__ == "__main__":
    main()
