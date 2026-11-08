"""Receipt use cases: creation on approval, ARCA emission and delivery (C-14).

Design D1/D4/D5: the receipt row is the durable job. Creation is idempotent by
`cobro_id`; emission claims the row with a five-minute token, calls the provider
outside the database transaction and persists the result only while the claim is
still valid. A manual retry resets the attempts and re-enqueues the job.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.clinica import auditar
from app.core.queues import ARCA_EMITIR, try_enqueue
from app.core.settings import Settings
from app.domain.fiscal import (
    AMBIENTE_HOMOLOGACION,
    calcular_proximo_intento,
    construir_qr_fiscal,
    construir_qr_interno,
    fecha_emision_local,
    tipo_comprobante,
)
from app.infrastructure.arca import ArcaClient, DatosReceptor, ResultadoEmision
from app.infrastructure.uow import UnitOfWork
from app.infrastructure.whatsapp import WhatsAppClient
from app.models.caja import Cobro
from app.models.fiscal import Comprobante, ComprobanteEnvio
from app.models.security import Usuario


@dataclass(frozen=True)
class ConfiguracionFiscal:
    """Issuer configuration: fixed point of sale and numbering policy (D2)."""

    cuit: str
    punto_venta: int = 1
    condicion_emisor: str = "responsable_inscripto"
    max_intentos: int = 5
    claim_timeout_seconds: int = 300


def configuracion_fiscal(settings: Settings) -> ConfiguracionFiscal:
    """Build the receipt configuration from the environment (D13)."""
    return ConfiguracionFiscal(
        cuit=settings.arca_cuit,
        punto_venta=settings.arca_punto_venta,
        condicion_emisor=settings.arca_condicion_emisor,
        max_intentos=settings.arca_max_intentos,
    )


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _sqlstate(error: BaseException) -> str | None:
    original = getattr(error, "orig", error)
    return getattr(original, "sqlstate", None) or getattr(
        original, "pgcode", None
    )


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail
    )


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=detail
    )


async def _resolver_comprobante(
    uow: UnitOfWork, consultorio_id: uuid.UUID, comprobante_id: uuid.UUID
) -> Comprobante:
    comprobante = await uow.comprobantes.get(comprobante_id)
    if (
        comprobante is None
        or comprobante.consultorio_id != consultorio_id
        or comprobante.deleted_at is not None
    ):
        raise _not_found("Comprobante no encontrado")
    return comprobante


async def crear_para_cobro(
    uow: UnitOfWork,
    *,
    cobro: Cobro,
    config: ConfiguracionFiscal,
    usuario_id: uuid.UUID | None,
    ip: str | None = None,
    dispositivo: str | None = None,
    redis_client: object | None = None,
) -> Comprobante | None:
    """Create the unique internal receipt of an approved payment (D1).

    Repeating the call returns the existing row without a second number or
    audit. A payment that is not approved never gets a receipt.
    """
    existente = await uow.comprobantes.get_by_cobro(cobro.id)
    if existente is not None:
        return existente
    if cobro.estado != "aprobado":
        return None

    paciente = await uow.pacientes.get(cobro.paciente_id)
    if paciente is None:  # pragma: no cover - FK guarantees it
        raise RuntimeError("El cobro no tiene un paciente válido")

    try:
        tipo = tipo_comprobante(config.condicion_emisor)
    except ValueError as error:
        raise _unprocessable(str(error)) from error

    numero_interno = await uow.secuencias_comprobantes.siguiente_interno(
        cobro.consultorio_id, config.punto_venta
    )
    fecha = fecha_emision_local(_ahora())
    comprobante_id = uuid.uuid4()
    comprobante = Comprobante(
        id=comprobante_id,
        consultorio_id=cobro.consultorio_id,
        cobro_id=cobro.id,
        paciente_id=cobro.paciente_id,
        tipo=tipo,
        ambiente=AMBIENTE_HOMOLOGACION,
        estado="pendiente",
        numero_interno=numero_interno,
        punto_venta=config.punto_venta,
        qr_interno=construir_qr_interno(
            comprobante_id=comprobante_id,
            numero_interno=numero_interno,
            importe=cobro.monto,
            fecha=fecha,
        ),
        receptor_nombre=f"{paciente.apellido}, {paciente.nombre}",
        receptor_documento=paciente.dni,
        receptor_tipo_documento="DNI",
        condicion_fiscal_receptor="consumidor_final",
        condicion_fiscal_emisor=config.condicion_emisor,
        importe_total=cobro.monto,
        fecha_emision=fecha,
        intentos=0,
    )
    try:
        await uow.comprobantes.add(comprobante)
    except IntegrityError as error:
        if _sqlstate(error) == "23505":
            existente = await uow.comprobantes.get_by_cobro(cobro.id)
            if existente is not None:
                return existente
        raise

    await auditar(
        uow,
        accion="comprobante.crear",
        entidad="comprobante",
        entidad_id=comprobante.id,
        usuario_id=usuario_id,
        ip=ip,
        dispositivo=dispositivo,
    )
    if redis_client is not None:
        await try_enqueue(redis_client, ARCA_EMITIR, str(comprobante.id))
    return comprobante


@dataclass(frozen=True)
class _Emision:
    """Detached snapshot needed for the provider call outside the transaction."""

    id: uuid.UUID
    tipo: str
    punto_venta: int
    importe: Decimal
    receptor: DatosReceptor


def _snapshot(comprobante: Comprobante) -> _Emision:
    return _Emision(
        id=comprobante.id,
        tipo=comprobante.tipo,
        punto_venta=comprobante.punto_venta,
        importe=comprobante.importe_total,
        receptor=DatosReceptor(
            nombre=comprobante.receptor_nombre,
            documento=comprobante.receptor_documento,
            tipo_documento=comprobante.receptor_tipo_documento,
            condicion_fiscal=comprobante.condicion_fiscal_receptor,
        ),
    )


async def procesar_comprobante(
    session_factory: async_sessionmaker[AsyncSession],
    cliente: ArcaClient,
    comprobante_id: uuid.UUID,
    *,
    config: ConfiguracionFiscal,
    ahora: datetime | None = None,
) -> Comprobante | None:
    """Claim one receipt, emit it outside a transaction and persist the result.

    Two short transactions surround the provider call (D4). If the claim is not
    ours, the result is discarded; the stable idempotency key returns the same
    CAE on the next attempt.
    """
    momento = ahora or _ahora()
    token = uuid.uuid4()
    async with UnitOfWork(session_factory) as uow:
        reclamado = await uow.comprobantes.reclamar(
            comprobante_id,
            token=token,
            ahora=momento,
            claim_timeout_seconds=config.claim_timeout_seconds,
        )
        if reclamado is None:
            # Already emitted: return the existing authorization (no new CAE).
            actual = await uow.comprobantes.get(comprobante_id)
            if actual is not None and actual.estado == "emitido":
                return actual
            return None
        emision = _snapshot(reclamado)

    resultado = None
    error: BaseException | None = None
    try:
        resultado = await cliente.emitir(
            clave_idempotencia=str(emision.id),
            tipo=emision.tipo,
            punto_venta=emision.punto_venta,
            importe=emision.importe,
            receptor=emision.receptor,
        )
    except Exception as exc:  # noqa: BLE001 - provider boundary
        error = exc

    async with UnitOfWork(session_factory) as uow:
        comprobante = await uow.comprobantes.get(comprobante_id)
        if (
            comprobante is None
            or comprobante.claim_token != token
            or comprobante.estado != "pendiente"
        ):
            return comprobante

        if resultado is not None:
            await _persistir_emision(
                uow, comprobante, resultado, config, momento
            )
            await auditar(
                uow,
                accion="comprobante.emitir",
                entidad="comprobante",
                entidad_id=comprobante.id,
                usuario_id=None,
            )
        else:
            await _persistir_fallo(
                uow, comprobante, error, config, momento
            )
            await auditar(
                uow,
                accion="comprobante.emitir_fallido",
                entidad="comprobante",
                entidad_id=comprobante.id,
                usuario_id=None,
            )
        await uow.session.flush()
        return comprobante


async def _persistir_emision(
    uow: UnitOfWork,
    comprobante: Comprobante,
    resultado: ResultadoEmision,
    config: ConfiguracionFiscal,
    momento: datetime,
) -> None:
    numero_fiscal = await uow.secuencias_comprobantes.siguiente_fiscal(
        comprobante.consultorio_id, comprobante.punto_venta
    )
    comprobante.numero_fiscal = numero_fiscal
    comprobante.cae = resultado.cae
    comprobante.cae_vencimiento = resultado.cae_vencimiento
    comprobante.qr_fiscal = construir_qr_fiscal(
        cuit=config.cuit,
        punto_venta=comprobante.punto_venta,
        tipo=comprobante.tipo,
        numero_fiscal=numero_fiscal,
        importe=comprobante.importe_total,
        cae=resultado.cae,
        fecha=fecha_emision_local(momento),
        documento_receptor=comprobante.receptor_documento,
        tipo_documento_receptor="96",
    )
    comprobante.fecha_emision_fiscal = momento
    comprobante.estado = "emitido"
    comprobante.proximo_intento = None
    comprobante.ultimo_error = None
    comprobante.claim_token = None
    comprobante.reclamado_at = None
    comprobante.respuesta_proveedor = {
        "cae": resultado.cae,
        "cae_vencimiento": resultado.cae_vencimiento.isoformat(),
    }


async def _persistir_fallo(
    uow: UnitOfWork,
    comprobante: Comprobante,
    error: BaseException | None,
    config: ConfiguracionFiscal,
    momento: datetime,
) -> None:
    comprobante.intentos += 1
    comprobante.ultimo_error = (
        str(error)[:1000] if error is not None else "Error desconocido de ARCA"
    )
    comprobante.claim_token = None
    comprobante.reclamado_at = None
    if comprobante.intentos >= config.max_intentos:
        comprobante.estado = "fallido"
        comprobante.proximo_intento = None
    else:
        comprobante.proximo_intento = calcular_proximo_intento(
            comprobante.intentos, ahora=momento
        )


async def listar_comprobantes(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    cobro_id: uuid.UUID | None = None,
    paciente_id: uuid.UUID | None = None,
    estado: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    tipo: str | None = None,
) -> list[Comprobante]:
    """Declared consult filters, newest first (D13)."""
    return await uow.comprobantes.list_filtrado(
        consultorio_id,
        cobro_id=cobro_id,
        paciente_id=paciente_id,
        estado=estado,
        desde=desde,
        hasta=hasta,
        tipo=tipo,
    )


async def obtener_comprobante(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    comprobante_id: uuid.UUID,
) -> Comprobante:
    return await _resolver_comprobante(uow, consultorio_id, comprobante_id)


async def enviar_comprobante(
    uow: UnitOfWork,
    cliente: WhatsAppClient,
    *,
    consultorio_id: uuid.UUID,
    comprobante_id: uuid.UUID,
    canal: str,
    destino: str | None,
    usuario: Usuario,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> tuple[ComprobanteEnvio, bool]:
    """Persist one simulated WhatsApp delivery of an emitted receipt (D10).

    The second attempt for the same channel returns the existing row and does
    not duplicate the audit entry.
    """
    comprobante = await _resolver_comprobante(
        uow, consultorio_id, comprobante_id
    )
    if comprobante.estado != "emitido":
        raise _conflict(
            "El comprobante todavía no tiene una factura fiscal"
        )

    existente = await uow.comprobantes_envios.get_por_canal(
        comprobante.id, canal
    )
    if existente is not None:
        return existente, False

    destino_final = (destino or "").strip()
    if not destino_final:
        paciente = await uow.pacientes.get(comprobante.paciente_id)
        if paciente is None or not paciente.telefono:
            raise _unprocessable(
                "El comprobante no tiene un destino válido"
            )
        destino_final = paciente.telefono

    variables = {
        "numero": comprobante.numero_fiscal,
        "cae": comprobante.cae,
        "importe": str(comprobante.importe_total),
        "qr": comprobante.qr_fiscal,
    }
    estado_envio = "registrado"
    proveedor_id = None
    error = None
    try:
        proveedor_id = await cliente.enviar(
            destino_final, "factura", variables
        )
    except Exception as exc:  # noqa: BLE001 - provider boundary
        estado_envio = "fallido"
        error = str(exc)[:1000]

    envio = await uow.comprobantes_envios.add(
        ComprobanteEnvio(
            comprobante_id=comprobante.id,
            canal=canal,
            destino=destino_final,
            estado=estado_envio,
            proveedor_mensaje_id=proveedor_id,
            error=error,
            creado_por=usuario.id,
        )
    )
    await auditar(
        uow,
        accion="comprobante.enviar",
        entidad="comprobante",
        entidad_id=comprobante.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    return envio, True


async def reintentar_comprobante(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    comprobante_id: uuid.UUID,
    usuario: Usuario,
    redis_client: object | None = None,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> Comprobante:
    """Reset a pending/failed receipt and enqueue it; emitted is a no-op (D5)."""
    comprobante = await _resolver_comprobante(
        uow, consultorio_id, comprobante_id
    )
    if comprobante.estado == "emitido":
        return comprobante
    if comprobante.estado not in {"pendiente", "fallido"}:
        raise _conflict("El comprobante no admite reintento")

    comprobante.estado = "pendiente"
    comprobante.intentos = 0
    comprobante.proximo_intento = None
    comprobante.ultimo_error = None
    comprobante.claim_token = None
    comprobante.reclamado_at = None
    await uow.session.flush()
    await auditar(
        uow,
        accion="comprobante.reintentar",
        entidad="comprobante",
        entidad_id=comprobante.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    if redis_client is not None:
        await try_enqueue(redis_client, ARCA_EMITIR, str(comprobante.id))
    return comprobante
