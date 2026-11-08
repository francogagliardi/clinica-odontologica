"""Worker entrypoints: reminders, WhatsApp sender and ARCA issuer (C-09/C-14).

Usage:
    python -m app.workers recordatorios
    python -m app.workers whatsapp
    python -m app.workers arca [--once]
"""

import asyncio
import sys
import uuid
from datetime import datetime, timezone

import redis.asyncio as redis_async
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.comprobantes import (
    configuracion_fiscal,
    procesar_comprobante,
)
from app.application.lista_espera import procesar_ofertas_vencidas
from app.application.recordatorios import (
    procesar_entrante,
    procesar_reintentos,
    procesar_vencidos,
)
from app.core.queues import ARCA_EMITIR, WHATSAPP_SEND, get_redis_client
from app.core.settings import Settings, load_settings
from app.infrastructure.arca import ArcaClient, get_arca_client
from app.infrastructure.db import create_engine, create_session_factory
from app.infrastructure.uow import UnitOfWork
from app.infrastructure.whatsapp import get_whatsapp_client

_MODOS = ("recordatorios", "whatsapp", "arca")


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


async def run_once_arca(
    settings: Settings,
    *,
    cliente: ArcaClient | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    redis_client: object | None = None,
    timeout: int = 1,
    ahora: datetime | None = None,
) -> int:
    """Pop one job and sweep due receipts, tolerating an unavailable Redis.

    The receipt row is the source of truth (R-06): if the queue is empty, the
    BRPOP fails or the message was duplicated, the sweep still retries every
    `pendiente` whose backoff elapsed.
    """
    engine = None
    if session_factory is None:
        engine = create_engine(settings.database_url)
        session_factory = create_session_factory(engine)

    cliente_arca = cliente or get_arca_client(settings)
    redis = redis_client
    owns_redis = redis is None
    if redis is None:
        redis = get_redis_client(settings.redis_url)

    momento = ahora or datetime.now(timezone.utc)
    config = configuracion_fiscal(settings)
    procesados = 0
    job_id: uuid.UUID | None = None
    try:
        job = None
        try:
            job = await redis.brpop(ARCA_EMITIR, timeout=timeout)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - Redis is only an accelerator
            job = None
        if job is not None:
            _, raw_id = job
            try:
                job_id = uuid.UUID(raw_id)
            except (TypeError, ValueError):
                job_id = None
            if job_id is not None:
                emitido = await procesar_comprobante(
                    session_factory,
                    cliente_arca,
                    job_id,
                    config=config,
                    ahora=momento,
                )
                if emitido is not None:
                    procesados += 1

        async with UnitOfWork(session_factory) as uow:
            pendientes = await uow.comprobantes.list_pendientes_vencidos(
                momento,
                limite=100,
                claim_timeout_seconds=config.claim_timeout_seconds,
            )
            ids = [
                comprobante.id
                for comprobante in pendientes
                if comprobante.id != job_id
            ]
        for comprobante_id in ids:
            emitido = await procesar_comprobante(
                session_factory,
                cliente_arca,
                comprobante_id,
                config=config,
                ahora=momento,
            )
            if emitido is not None:
                procesados += 1
        return procesados
    finally:
        if owns_redis:
            await redis.aclose()  # type: ignore[union-attr]
        if engine is not None:
            await engine.dispose()


async def loop_arca(settings: Settings) -> None:  # pragma: no cover
    while True:
        await run_once_arca(settings)
        await asyncio.sleep(settings.arca_worker_interval_seconds)


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    modo = args[0] if args else ""
    if modo not in _MODOS:
        raise SystemExit(
            "Uso: python -m app.workers "
            "[recordatorios|whatsapp|arca] [--once]"
        )
    settings = load_settings()
    if "--once" in args:
        if modo == "recordatorios":
            asyncio.run(run_once_recordatorios(settings))
        elif modo == "whatsapp":
            asyncio.run(run_once_whatsapp(settings, timeout=1))
        else:
            asyncio.run(run_once_arca(settings, timeout=1))
        return
    loop = {
        "recordatorios": loop_recordatorios,
        "whatsapp": loop_whatsapp,
        "arca": loop_arca,
    }[modo]
    asyncio.run(loop(settings))


if __name__ == "__main__":
    main()
