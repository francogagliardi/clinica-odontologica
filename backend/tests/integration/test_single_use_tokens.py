"""Integration tests for single-use public link tokens (C-03, R-04, RN-NO-03)."""

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.tokens import (
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenNotFoundError,
    TokenPurposeError,
    consume_single_use_token,
    create_single_use_token,
    hash_token,
    verify_single_use_token,
)
from app.models.token import TokenUnSoloUso


@pytest.mark.anyio
async def test_emision_y_consulta_token_valido(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        issued = await create_single_use_token(
            session=session,
            tipo="confirmacion_turno",
            entidad_tipo="turno",
            entidad_id="turno-uuid-123",
            expires_minutes=60,
        )
        assert issued.token
        registro = issued.registro
        assert registro.tipo == "confirmacion_turno"
        assert registro.entidad_id == "turno-uuid-123"
        assert registro.usado is False
        assert registro.usado_at is None
        assert registro.expira_at > datetime.now(timezone.utc)

        verified = await verify_single_use_token(
            session, issued.token, expected_tipo="confirmacion_turno"
        )
        assert verified.id == registro.id
        assert verified.usado is False


@pytest.mark.anyio
async def test_token_se_guarda_hasheado_en_reposo(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        issued = await create_single_use_token(
            session=session,
            tipo="pago_seña",
            entidad_tipo="turno",
            entidad_id="turno-hash",
            expires_minutes=30,
        )
        await session.commit()

        stored = (
            await session.scalars(select(TokenUnSoloUso))
        ).all()
        assert len(stored) == 1
        assert stored[0].token_hash == hash_token(issued.token)
        assert stored[0].token_hash != issued.token
        assert len(stored[0].token_hash) == 64
        # The raw token cannot be recovered from the database.
        assert issued.token not in stored[0].token_hash

        second = await create_single_use_token(
            session=session,
            tipo="pago_seña",
            entidad_tipo="turno",
            entidad_id="turno-hash-2",
            expires_minutes=30,
        )
        assert second.registro.token_hash != stored[0].token_hash
        assert second.registro.token_hash == hash_token(second.token)


@pytest.mark.anyio
async def test_token_inexistente_falla_sin_filtrar_el_valor(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    raw = "token-que-no-existe-1234567890"
    async with session_factory() as session:
        with pytest.raises(TokenNotFoundError) as excinfo:
            await verify_single_use_token(session, raw)
        assert raw not in str(excinfo.value)


@pytest.mark.anyio
async def test_token_de_otro_proposito_es_rechazado(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        issued = await create_single_use_token(
            session=session,
            tipo="recordatorio",
            entidad_tipo="turno",
            entidad_id="turno-otro-proposito",
            expires_minutes=30,
        )

        with pytest.raises(TokenPurposeError):
            await verify_single_use_token(
                session, issued.token, expected_tipo="confirmacion_turno"
            )

        with pytest.raises(TokenPurposeError):
            await consume_single_use_token(
                session, issued.token, expected_tipo="confirmacion_turno"
            )

        # The rejected attempt must not have consumed the token.
        verified = await verify_single_use_token(
            session, issued.token, expected_tipo="recordatorio"
        )
        assert verified.usado is False


@pytest.mark.anyio
async def test_token_vencido_falla(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        issued = await create_single_use_token(
            session=session,
            tipo="recordatorio",
            entidad_tipo="turno",
            entidad_id="turno-exp-123",
            expires_minutes=-10,
        )
        await session.commit()

        with pytest.raises(TokenExpiredError):
            await verify_single_use_token(session, issued.token)

        with pytest.raises(TokenExpiredError):
            await consume_single_use_token(session, issued.token)


@pytest.mark.anyio
async def test_consumo_exitoso_y_reutilizacion_rechazada(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        issued = await create_single_use_token(
            session=session,
            tipo="cancelacion_turno",
            entidad_tipo="turno",
            entidad_id="turno-abc",
            expires_minutes=30,
        )
        await session.commit()

        consumed = await consume_single_use_token(session, issued.token)
        await session.commit()
        assert consumed.usado is True
        assert consumed.usado_at is not None

        with pytest.raises(TokenAlreadyUsedError):
            await consume_single_use_token(session, issued.token)

        with pytest.raises(TokenAlreadyUsedError):
            await verify_single_use_token(session, issued.token)


@pytest.mark.anyio
async def test_consumo_concurrente_exactamente_uno_tiene_exito(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        issued = await create_single_use_token(
            session=session,
            tipo="pago_seña",
            entidad_tipo="turno",
            entidad_id="turno-concurrent",
            expires_minutes=30,
        )
        await session.commit()
        raw_token = issued.token

    async def try_consume() -> str:
        async with session_factory() as sess:
            try:
                await consume_single_use_token(sess, raw_token)
                await sess.commit()
                return "SUCCESS"
            except TokenAlreadyUsedError:
                return "ALREADY_USED"

    results = sorted(await asyncio.gather(try_consume(), try_consume()))
    assert results == ["ALREADY_USED", "SUCCESS"]
