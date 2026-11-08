"""Builders for C-15 exportation tests (fictional data only).

The dataset covers every entity of the ERD once, including a 2 MB clinical
attachment and deliberate secret markers that must never appear in the ZIP.
"""

import csv
import io
import json
import uuid
import zipfile
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.agenda import ARGENTINA_OFFSET
from app.models import Exportacion, RegistroAuditoria
from tests.integration.caja_helpers import (
    insertar_caja_db,
    insertar_cobro_db,
    insertar_movimiento_db,
)
from tests.integration.clinica_helpers import (
    insertar_consentimiento_db,
    insertar_evolucion_db,
    insertar_historia_db,
    insertar_hallazgo_db,
    insertar_odontograma_db,
)
from tests.integration.comprobantes_helpers import FakeRedis, fiscal_config
from tests.integration.fiscal_helpers import (
    CAE_PRUEBA,
    insertar_comprobante_db,
    insertar_envio_db,
    insertar_item_liquidacion_db,
    insertar_liquidacion_db,
)
from tests.integration.lista_espera_helpers import insertar_entrada
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.presupuestos_helpers import (
    insertar_item_db,
    insertar_presupuesto_db,
    setup_presupuestos,
)

ADJUNTO_BYTES = b"\x89PNG\r\n\x1a\n" + b"exportacion" * 200_000
ADJUNTO_NOMBRE = "radiografia 2026.png"
SECRETO_TOKEN = "token-publico-super-secreto-c15"
SECRETO_LINK = "https://mp.test/link-pago-secreto-c15"
SECRETO_PROVEEDOR = "proveedor-pago-secreto-c15"
SECRETO_PREFERENCIA = "proveedor-preferencia-secreta-c15"
SECRETO_CLAIM = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
SECRETO_PAYLOAD = "payload-envio-secreto-c15"
SECRETO_RESPUESTA = "respuesta-proveedor-secreta-c15"
SECRETO_MENSAJE = "proveedor-mensaje-secreto-c15"
SECRETO_WA = "payload-whatsapp-secreto-c15"
SECRETO_WEBHOOK = "webhook-secret-c15"
AHORA = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


async def setup_exportacion_completa(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Clinical, commercial, fiscal, cash, messaging and audit data of a patient."""
    data = await setup_presupuestos(session_factory)
    consultorio_id = data["consultorio_id"]
    admin = data["actores"]["administrador"]
    odontologo = data["actores"]["odontologo"]
    paciente = data["paciente_propio"]
    profesional = data["profesional"]
    sillon = data["sillon"]
    turno_id = data["turnos"]["propio"]
    prestacion = data["prestaciones"]["CONS"]
    obra_social_id = data["obra_social_demo_id"]

    historia_id = await insertar_historia_db(
        session_factory,
        consultorio_id=consultorio_id,
        paciente_id=paciente.id,
        abierta_por=odontologo.id,
    )
    evolucion_id = await insertar_evolucion_db(
        session_factory,
        historia_id=historia_id,
        profesional_id=profesional.id,
        creado_por=odontologo.id,
        texto="Evolución firmada exportable",
        firmada=True,
        firmada_por=odontologo.id,
        fecha_firma=AHORA,
    )
    odontograma_id = await insertar_odontograma_db(
        session_factory, historia_id=historia_id, version=1
    )
    hallazgo_id = await insertar_hallazgo_db(
        session_factory,
        odontograma_id=odontograma_id,
        pieza=16,
        cara="mesial",
        estado="caries",
        diagnostico="Caries oclusal",
        cie10="K02.1",
    )
    consentimiento_id = await insertar_consentimiento_db(
        session_factory,
        consultorio_id=consultorio_id,
        paciente_id=paciente.id,
        registrado_por=odontologo.id,
    )
    adjunto_id = uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO adjuntos "
                "(id, historia_id, nombre, mime, tamano, contenido, "
                "subido_por) VALUES (:id, :historia_id, :nombre, 'image/png', "
                ":tamano, :contenido, :subido_por)"
            ),
            {
                "id": adjunto_id,
                "historia_id": historia_id,
                "nombre": ADJUNTO_NOMBRE,
                "tamano": len(ADJUNTO_BYTES),
                "contenido": ADJUNTO_BYTES,
                "subido_por": odontologo.id,
            },
        )

    presupuesto_id = await insertar_presupuesto_db(
        session_factory,
        consultorio_id=consultorio_id,
        paciente_id=paciente.id,
        profesional_id=profesional.id,
        creado_por=admin.id,
        estado="finalizado",
        subtotal="20000.00",
        cobertura_calculada="20000.00",
        copago="0.00",
    )
    item_presupuesto_id = await insertar_item_db(
        session_factory,
        presupuesto_id=presupuesto_id,
        prestacion_id=prestacion.id,
        cantidad=1,
        precio_unitario="20000.00",
        cobertura_item="20000.00",
        copago_item="0.00",
    )
    cobro_id = await insertar_cobro_db(
        session_factory,
        consultorio_id=consultorio_id,
        paciente_id=paciente.id,
        tipo="tratamiento",
        medio="mercadopago",
        estado="aprobado",
        monto="20000.00",
        presupuesto_id=presupuesto_id,
        creado_por=admin.id,
        proveedor_pago_id=SECRETO_PROVEEDOR,
        proveedor_preferencia_id=SECRETO_PREFERENCIA,
        link_pago=SECRETO_LINK,
        fecha_operacion=date(2026, 11, 4),
    )
    caja_id = await insertar_caja_db(
        session_factory,
        consultorio_id=consultorio_id,
        fecha=date(2026, 11, 4),
        monto_apertura="0.00",
    )
    movimiento_id = await insertar_movimiento_db(
        session_factory,
        caja_id=caja_id,
        tipo="ingreso",
        concepto="Cobro exportable",
        monto="20000.00",
        medio="mercadopago",
        cobro_id=cobro_id,
        creado_por=admin.id,
    )

    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "UPDATE turnos SET token_publico = :token WHERE id = :id"
            ),
            {"token": SECRETO_TOKEN, "id": turno_id},
        )
        await session.execute(
            text(
                "UPDATE cobros SET link_pago = :link, "
                "proveedor_pago_id = :prov, "
                "proveedor_preferencia_id = :pref WHERE id = :id"
            ),
            {
                "link": SECRETO_LINK,
                "prov": SECRETO_PROVEEDOR,
                "pref": SECRETO_PREFERENCIA,
                "id": cobro_id,
            },
        )

    comprobante_id = await insertar_comprobante_db(
        session_factory,
        consultorio_id=consultorio_id,
        cobro_id=cobro_id,
        paciente_id=paciente.id,
        estado="emitido",
        numero_interno=1,
        numero_fiscal=1,
        cae=CAE_PRUEBA,
    )
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "UPDATE comprobantes SET claim_token = :claim, "
                "payload_envio = CAST(:payload AS jsonb), "
                "respuesta_proveedor = CAST(:respuesta AS jsonb) "
                "WHERE id = :id"
            ),
            {
                "claim": SECRETO_CLAIM,
                "payload": json.dumps({"secreto": SECRETO_PAYLOAD}),
                "respuesta": json.dumps({"secreto": SECRETO_RESPUESTA}),
                "id": comprobante_id,
            },
        )
    envio_id = await insertar_envio_db(
        session_factory,
        comprobante_id=comprobante_id,
        proveedor_mensaje_id=SECRETO_MENSAJE,
        creado_por=admin.id,
    )

    liquidacion_id = await insertar_liquidacion_db(
        session_factory,
        consultorio_id=consultorio_id,
        obra_social_id=obra_social_id,
        creado_por=admin.id,
        desde=date(2026, 11, 1),
        hasta=date(2026, 11, 30),
        estado="borrador",
        total_cobertura="20000.00",
        cantidad_practicas=1,
    )
    item_liquidacion_id = await insertar_item_liquidacion_db(
        session_factory,
        liquidacion_id=liquidacion_id,
        item_presupuesto_id=item_presupuesto_id,
        presupuesto_id=presupuesto_id,
        cobro_id=cobro_id,
        prestacion_id=prestacion.id,
        prestacion_codigo="CONS",
        cantidad=1,
        cobertura_item="20000.00",
    )

    recordatorio_id = uuid.uuid4()
    mensaje_id = uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO recordatorios "
                "(id, turno_id, ventana, programado_para, estado) "
                "VALUES (:id, :turno_id, '48h', :programado, 'pendiente')"
            ),
            {
                "id": recordatorio_id,
                "turno_id": turno_id,
                "programado": AHORA,
            },
        )
        await session.execute(
            text(
                "INSERT INTO mensajes_whatsapp "
                "(id, recordatorio_id, turno_id, plantilla, estado_envio, "
                "respuesta, proveedor_mensaje_id, payload) "
                "VALUES (:id, :recordatorio_id, :turno_id, 'recordatorio', "
                "'enviado', 'ninguna', :proveedor, CAST(:payload AS jsonb))"
            ),
            {
                "id": mensaje_id,
                "recordatorio_id": recordatorio_id,
                "turno_id": turno_id,
                "proveedor": SECRETO_MENSAJE,
                "payload": json.dumps({"secreto": SECRETO_WA}),
            },
        )
        session.add(
            RegistroAuditoria(
                usuario_id=admin.id,
                accion="turno.crear",
                entidad="turno",
                entidad_id=str(turno_id),
            )
        )

    entrada_id = await insertar_entrada(
        session_factory,
        consultorio_id=consultorio_id,
        paciente_id=paciente.id,
        prestacion_id=prestacion.id,
        profesional_id=profesional.id,
    )

    return {
        **data,
        "paciente": paciente,
        "sillon": sillon,
        "historia_id": historia_id,
        "evolucion_id": evolucion_id,
        "odontograma_id": odontograma_id,
        "hallazgo_id": hallazgo_id,
        "consentimiento_id": consentimiento_id,
        "adjunto_id": adjunto_id,
        "presupuesto_id": presupuesto_id,
        "item_presupuesto_id": item_presupuesto_id,
        "cobro_id": cobro_id,
        "caja_id": caja_id,
        "movimiento_id": movimiento_id,
        "comprobante_id": comprobante_id,
        "envio_id": envio_id,
        "liquidacion_id": liquidacion_id,
        "item_liquidacion_id": item_liquidacion_id,
        "recordatorio_id": recordatorio_id,
        "mensaje_id": mensaje_id,
        "entrada_id": entrada_id,
        "secreto_webhook": SECRETO_WEBHOOK,
    }


async def crear_paciente_vacio(
    session_factory: async_sessionmaker[AsyncSession],
    consultorio_id: uuid.UUID,
) -> uuid.UUID:
    paciente = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Vacío",
        apellido="SinClínica",
        dni=f"4{uuid.uuid4().int % 10_000_000:07d}",
        telefono="+5491177779999",
    )
    return paciente.id


async def leer_exportacion(session_factory, exportacion_id: uuid.UUID):
    async with session_factory() as session:
        return await session.get(Exportacion, exportacion_id)


def config_exportacion(**overrides: object):
    from app.application.exportaciones import ConfiguracionExportacion

    base: dict[str, object] = {
        "max_filas": 50000,
        "max_bytes": 67108864,
        "max_intentos": 3,
        "claim_timeout_seconds": 300,
    }
    base.update(overrides)
    return ConfiguracionExportacion(**base)  # type: ignore[arg-type]


def unzip(contenido: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(contenido)) as archivo:
        return {info.filename: archivo.read(info) for info in archivo.infolist()}


def datos_json(contenido: bytes) -> dict[str, object]:
    return json.loads(unzip(contenido)["datos.json"].decode("utf-8"))


def manifiesto_json(contenido: bytes) -> dict[str, object]:
    return json.loads(unzip(contenido)["manifiesto.json"].decode("utf-8"))


def filas_csv(contenido: bytes, entidad: str) -> list[dict[str, str]]:
    texto = unzip(contenido)[f"csv/{entidad}.csv"].decode("utf-8")
    return list(csv.DictReader(io.StringIO(texto)))


def textos_del_zip(contenido: bytes) -> dict[str, str]:
    """Every non-binary entry as text, keyed by its ZIP name."""
    textos: dict[str, str] = {}
    for nombre, datos in unzip(contenido).items():
        if nombre.startswith("adjuntos/"):
            continue
        textos[nombre] = datos.decode("utf-8", errors="replace")
    return textos


__all__ = [
    "ADJUNTO_BYTES",
    "ADJUNTO_NOMBRE",
    "AHORA",
    "FakeRedis",
    "SECRETO_CLAIM",
    "SECRETO_LINK",
    "SECRETO_MENSAJE",
    "SECRETO_PAYLOAD",
    "SECRETO_PREFERENCIA",
    "SECRETO_PROVEEDOR",
    "SECRETO_RESPUESTA",
    "SECRETO_TOKEN",
    "SECRETO_WA",
    "config_exportacion",
    "crear_paciente_vacio",
    "datos_json",
    "filas_csv",
    "fiscal_config",
    "leer_exportacion",
    "manifiesto_json",
    "setup_exportacion_completa",
    "textos_del_zip",
    "unzip",
]
