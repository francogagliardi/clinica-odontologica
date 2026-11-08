"""Builders for billing/ARCA and settlement integration tests (fictional data).

Every helper writes with SQL inside its own short transaction, mirroring the
C-13/C-12 builders. Defaults describe one coherent row of each table so a test
overrides only the field under scrutiny.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.integration.presupuestos_helpers import setup_presupuestos

FECHA_FISCAL = date(2026, 11, 4)
CAE_PRUEBA = "12345678901234"
QR_INTERNO_PRUEBA = "https://app.local/comprobantes/verificar?p=e30"
QR_FISCAL_PRUEBA = "https://www.afip.gob.ar/fe/qr/?p=e30"


async def setup_fiscal(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Clinical fixtures plus catalogue, agreements and patients with coverage."""
    return await setup_presupuestos(session_factory)


async def insertar_comprobante_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    consultorio_id: uuid.UUID,
    cobro_id: uuid.UUID,
    paciente_id: uuid.UUID,
    estado: str = "pendiente",
    tipo: str = "B",
    ambiente: str = "homologacion",
    numero_interno: int = 1,
    punto_venta: int = 1,
    numero_fiscal: int | None = None,
    cae: str | None = None,
    cae_vencimiento: date | None = None,
    qr_interno: str = QR_INTERNO_PRUEBA,
    qr_fiscal: str | None = None,
    receptor_nombre: str = "Demo, Paciente",
    receptor_documento: str = "42112001",
    receptor_tipo_documento: str = "DNI",
    condicion_fiscal_receptor: str = "consumidor_final",
    condicion_fiscal_emisor: str = "responsable_inscripto",
    importe_total: str = "10000.00",
    fecha_emision: date = FECHA_FISCAL,
    fecha_emision_fiscal: datetime | None = None,
    intentos: int = 0,
    proximo_intento: datetime | None = None,
    ultimo_error: str | None = None,
    claim_token: uuid.UUID | None = None,
    reclamado_at: datetime | None = None,
    comprobante_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Insert one receipt; an `emitido` row gets coherent fiscal fields."""
    if estado == "emitido":
        cae = CAE_PRUEBA if cae is None else cae
        cae_vencimiento = (
            date(2026, 11, 14)
            if cae_vencimiento is None
            else cae_vencimiento
        )
        numero_fiscal = (
            numero_interno if numero_fiscal is None else numero_fiscal
        )
        qr_fiscal = QR_FISCAL_PRUEBA if qr_fiscal is None else qr_fiscal
        fecha_emision_fiscal = (
            datetime(2026, 11, 4, 15, 0, tzinfo=timezone.utc)
            if fecha_emision_fiscal is None
            else fecha_emision_fiscal
        )
    if estado == "fallido" and ultimo_error is None:
        ultimo_error = "ARCA no disponible"

    comprobante_id = comprobante_id or uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO comprobantes "
                "(id, consultorio_id, cobro_id, paciente_id, tipo, ambiente, "
                "estado, numero_interno, punto_venta, numero_fiscal, cae, "
                "cae_vencimiento, qr_interno, qr_fiscal, receptor_nombre, "
                "receptor_documento, receptor_tipo_documento, "
                "condicion_fiscal_receptor, condicion_fiscal_emisor, "
                "importe_total, fecha_emision, fecha_emision_fiscal, "
                "intentos, proximo_intento, ultimo_error, claim_token, "
                "reclamado_at) "
                "VALUES (:id, :consultorio_id, :cobro_id, :paciente_id, "
                ":tipo, :ambiente, :estado, :numero_interno, :punto_venta, "
                ":numero_fiscal, :cae, :cae_vencimiento, :qr_interno, "
                ":qr_fiscal, :receptor_nombre, :receptor_documento, "
                ":receptor_tipo_documento, :condicion_fiscal_receptor, "
                ":condicion_fiscal_emisor, :importe_total, :fecha_emision, "
                ":fecha_emision_fiscal, :intentos, :proximo_intento, "
                ":ultimo_error, :claim_token, :reclamado_at)"
            ),
            {
                "id": comprobante_id,
                "consultorio_id": consultorio_id,
                "cobro_id": cobro_id,
                "paciente_id": paciente_id,
                "tipo": tipo,
                "ambiente": ambiente,
                "estado": estado,
                "numero_interno": numero_interno,
                "punto_venta": punto_venta,
                "numero_fiscal": numero_fiscal,
                "cae": cae,
                "cae_vencimiento": cae_vencimiento,
                "qr_interno": qr_interno,
                "qr_fiscal": qr_fiscal,
                "receptor_nombre": receptor_nombre,
                "receptor_documento": receptor_documento,
                "receptor_tipo_documento": receptor_tipo_documento,
                "condicion_fiscal_receptor": condicion_fiscal_receptor,
                "condicion_fiscal_emisor": condicion_fiscal_emisor,
                "importe_total": importe_total,
                "fecha_emision": fecha_emision,
                "fecha_emision_fiscal": fecha_emision_fiscal,
                "intentos": intentos,
                "proximo_intento": proximo_intento,
                "ultimo_error": ultimo_error,
                "claim_token": claim_token,
                "reclamado_at": reclamado_at,
            },
        )
    return comprobante_id


async def insertar_envio_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    comprobante_id: uuid.UUID,
    canal: str = "whatsapp",
    destino: str = "+5491177770201",
    estado: str = "registrado",
    proveedor_mensaje_id: str = "test-envio-1",
    error: str | None = None,
    creado_por: uuid.UUID | None = None,
    envio_id: uuid.UUID | None = None,
) -> uuid.UUID:
    envio_id = envio_id or uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO comprobantes_envios "
                "(id, comprobante_id, canal, destino, estado, "
                "proveedor_mensaje_id, error, creado_por) "
                "VALUES (:id, :comprobante_id, :canal, :destino, :estado, "
                ":proveedor_mensaje_id, :error, :creado_por)"
            ),
            {
                "id": envio_id,
                "comprobante_id": comprobante_id,
                "canal": canal,
                "destino": destino,
                "estado": estado,
                "proveedor_mensaje_id": proveedor_mensaje_id,
                "error": error,
                "creado_por": creado_por,
            },
        )
    return envio_id


async def insertar_liquidacion_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    consultorio_id: uuid.UUID,
    obra_social_id: uuid.UUID,
    creado_por: uuid.UUID,
    desde: date = FECHA_FISCAL,
    hasta: date = FECHA_FISCAL,
    estado: str = "borrador",
    total_cobertura: str = "6000.00",
    cantidad_practicas: int = 1,
    observaciones: str | None = None,
    cerrada_por: uuid.UUID | None = None,
    cerrada_at: datetime | None = None,
    liquidacion_id: uuid.UUID | None = None,
) -> uuid.UUID:
    if estado == "cerrada":
        cerrada_por = cerrada_por or creado_por
        cerrada_at = cerrada_at or datetime(
            2026, 11, 4, 16, 0, tzinfo=timezone.utc
        )
    liquidacion_id = liquidacion_id or uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO liquidaciones_obras_sociales "
                "(id, consultorio_id, obra_social_id, creado_por, desde, "
                "hasta, estado, total_cobertura, cantidad_practicas, "
                "observaciones, cerrada_por, cerrada_at) "
                "VALUES (:id, :consultorio_id, :obra_social_id, :creado_por, "
                ":desde, :hasta, :estado, :total_cobertura, "
                ":cantidad_practicas, :observaciones, :cerrada_por, "
                ":cerrada_at)"
            ),
            {
                "id": liquidacion_id,
                "consultorio_id": consultorio_id,
                "obra_social_id": obra_social_id,
                "creado_por": creado_por,
                "desde": desde,
                "hasta": hasta,
                "estado": estado,
                "total_cobertura": total_cobertura,
                "cantidad_practicas": cantidad_practicas,
                "observaciones": observaciones,
                "cerrada_por": cerrada_por,
                "cerrada_at": cerrada_at,
            },
        )
    return liquidacion_id


async def insertar_item_liquidacion_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    liquidacion_id: uuid.UUID,
    item_presupuesto_id: uuid.UUID,
    presupuesto_id: uuid.UUID,
    cobro_id: uuid.UUID,
    prestacion_id: uuid.UUID,
    prestacion_codigo: str = "CONS",
    pieza: int | None = None,
    cantidad: int = 1,
    cobertura_item: str = "6000.00",
    item_liquidacion_id: uuid.UUID | None = None,
) -> uuid.UUID:
    item_liquidacion_id = item_liquidacion_id or uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO items_liquidacion "
                "(id, liquidacion_id, item_presupuesto_id, presupuesto_id, "
                "cobro_id, prestacion_id, prestacion_codigo, pieza, "
                "cantidad, cobertura_item) "
                "VALUES (:id, :liquidacion_id, :item_presupuesto_id, "
                ":presupuesto_id, :cobro_id, :prestacion_id, "
                ":prestacion_codigo, :pieza, :cantidad, :cobertura_item)"
            ),
            {
                "id": item_liquidacion_id,
                "liquidacion_id": liquidacion_id,
                "item_presupuesto_id": item_presupuesto_id,
                "presupuesto_id": presupuesto_id,
                "cobro_id": cobro_id,
                "prestacion_id": prestacion_id,
                "prestacion_codigo": prestacion_codigo,
                "pieza": pieza,
                "cantidad": cantidad,
                "cobertura_item": cobertura_item,
            },
        )
    return item_liquidacion_id
