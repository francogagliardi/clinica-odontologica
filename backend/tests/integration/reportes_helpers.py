"""Builders for C-15 reports and exportation integration tests (fictional data).

The dataset is deterministic on purpose: every aggregate the repository tests
assert has an expected value written by hand, never a value recomputed with the
same SQL under test (design D15).
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.agenda import ARGENTINA_OFFSET
from tests.integration.caja_helpers import (
    insertar_caja_db,
    insertar_cobro_db,
    insertar_movimiento_db,
)
from tests.integration.fiscal_helpers import (
    insertar_item_liquidacion_db,
    insertar_liquidacion_db,
)
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.presupuestos_helpers import (
    insertar_item_db,
    insertar_presupuesto_db,
)
from tests.integration.recursos_helpers import (
    consultorio_demo_id,
    create_actor,
    create_profesional,
    create_sillon,
    seed_demo,
)
from tests.integration.turnos_helpers import insertar_turno_db
from tests.integration.clinica_helpers import otro_consultorio

ROLES = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)

# Agenda window: Monday 9 November 2026 to Friday 13 November 2026.
FECHA_DESDE = date(2026, 11, 9)
FECHA_HASTA = date(2026, 11, 13)
DESDE_UTC = datetime(2026, 11, 9, 3, 0, tzinfo=timezone.utc)
HASTA_UTC = datetime(2026, 11, 14, 3, 0, tzinfo=timezone.utc)
INICIO_LUNES = datetime(2026, 11, 9, 9, 0, tzinfo=ARGENTINA_OFFSET)

# Cash window: November 2026 (the payment date used by the caja fixtures).
FECHA_CAJA_CERRADA = date(2026, 11, 4)
FECHA_CAJA_ABIERTA = date(2026, 11, 5)
CAJA_DESDE = date(2026, 11, 1)
CAJA_HASTA = date(2026, 11, 30)
# Settlement payments are intentionally outside the cash window so they do
# not pollute the cobro aggregates of the caja report.
FECHA_COBRO_LIQUIDACION = date(2026, 10, 15)


async def setup_base(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Demo tenant plus every actor and no domain rows yet."""
    await seed_demo(session_factory)
    consultorio_id = await consultorio_demo_id(session_factory)
    actores = {
        rol: await create_actor(session_factory, rol) for rol in ROLES
    }
    return {"consultorio_id": consultorio_id, "actores": actores}


async def setup_exportaciones(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Tenant, actors and one own patient for exportation tests."""
    data = await setup_base(session_factory)
    consultorio_id = data["consultorio_id"]
    paciente = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Export",
        apellido="Demo",
        dni="42555777",
        telefono="+5491177770555",
    )
    return {**data, "paciente": paciente}


async def setup_reportes(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Deterministic agenda, cash and settlement dataset for C-15 reports.

    Agenda (Monday 9 to Friday 13 November 2026):

    - professional one: 09:00-13:00 Monday..Friday (240 min/day → 1200 min),
      nine appointments (5 attended incl. one sobreturno, 2 cancelled,
      1 absent, 1 reserved, 1 confirmed, 1 in room);
    - professional two: 09:00-12:00 Mondays only (180 min), one attended and
      one cancelled.

    Cash (November 2026): two approved cash payments (10000 + 5000), one
    approved Mercado Pago payment (8000) and four non-approved payments; one
    closed register on 4 November and one open register on 5 November, plus a
    register outside the range.
    """
    data = await setup_exportaciones(session_factory)
    consultorio_id = data["consultorio_id"]
    actores = data["actores"]
    admin = actores["administrador"]
    odontologo = actores["odontologo"]

    profesional = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-REP-1",
        usuario_id=odontologo.id,
        dias_atencion=(0, 1, 2, 3, 4),
        hora_desde=time(9, 0),
        hora_hasta=time(13, 0),
    )
    profesional_dos = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-REP-2",
        dias_atencion=(0,),
        hora_desde=time(9, 0),
        hora_hasta=time(12, 0),
    )
    sillon_a = await create_sillon(
        session_factory, consultorio_id, "Sillón Reportes A"
    )
    sillon_b = await create_sillon(
        session_factory, consultorio_id, "Sillón Reportes B"
    )

    paciente_uno = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Agenda",
        apellido="Reportes",
        dni="42555801",
        telefono="+5491177770801",
    )
    paciente_dos = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Caja",
        apellido="Reportes",
        dni="42555802",
        telefono="+5491177770802",
    )

    async def turno(
        *,
        dia: int,
        hora: int,
        estado: str,
        profesional_id: uuid.UUID,
        sillon_id: uuid.UUID,
        paciente_id: uuid.UUID,
        sobreturno: bool = False,
    ) -> uuid.UUID:
        inicio = INICIO_LUNES + timedelta(days=dia, hours=hora - 9)
        return await insertar_turno_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            profesional_id=profesional_id,
            sillon_id=sillon_id,
            inicio=inicio,
            fin=inicio + timedelta(hours=1),
            estado=estado,
            es_sobreturno=sobreturno,
        )

    turnos = {
        "lun_9_atendido": await turno(
            dia=0,
            hora=9,
            estado="atendido",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_uno.id,
        ),
        "lun_10_atendido": await turno(
            dia=0,
            hora=10,
            estado="atendido",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_uno.id,
        ),
        "lun_11_cancelado": await turno(
            dia=0,
            hora=11,
            estado="cancelado",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_uno.id,
        ),
        "lun_9_otro_atendido": await turno(
            dia=0,
            hora=9,
            estado="atendido",
            profesional_id=profesional_dos.id,
            sillon_id=sillon_b.id,
            paciente_id=paciente_dos.id,
        ),
        "lun_10_otro_cancelado": await turno(
            dia=0,
            hora=10,
            estado="cancelado",
            profesional_id=profesional_dos.id,
            sillon_id=sillon_b.id,
            paciente_id=paciente_dos.id,
        ),
        "mar_9_ausente": await turno(
            dia=1,
            hora=9,
            estado="ausente",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_uno.id,
        ),
        "mar_10_reservado": await turno(
            dia=1,
            hora=10,
            estado="reservado",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_uno.id,
        ),
        "mar_11_confirmado": await turno(
            dia=1,
            hora=11,
            estado="confirmado",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_uno.id,
        ),
        "mie_9_en_sala": await turno(
            dia=2,
            hora=9,
            estado="en_sala",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_uno.id,
        ),
        "mie_10_atendido": await turno(
            dia=2,
            hora=10,
            estado="atendido",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_uno.id,
        ),
        "mie_11_sobreturno": await turno(
            dia=2,
            hora=11,
            estado="atendido",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_dos.id,
            sobreturno=True,
        ),
    }

    caja_cerrada = await insertar_caja_db(
        session_factory,
        consultorio_id=consultorio_id,
        fecha=FECHA_CAJA_CERRADA,
        estado="cerrada",
        monto_apertura="10000.00",
        monto_sistema_efectivo="10000.00",
        monto_contado="10000.00",
        diferencia="0.00",
        cerrada_por=admin.id,
        cerrada_at=datetime(
            2026, 11, 4, 21, 0, tzinfo=timezone.utc
        ),
    )
    caja_abierta = await insertar_caja_db(
        session_factory,
        consultorio_id=consultorio_id,
        fecha=FECHA_CAJA_ABIERTA,
        estado="abierta",
        monto_apertura="5000.00",
    )
    caja_fuera = await insertar_caja_db(
        session_factory,
        consultorio_id=consultorio_id,
        fecha=date(2026, 10, 1),
        estado="abierta",
        monto_apertura="1000.00",
    )

    movimientos = {
        "ingreso_efectivo": await insertar_movimiento_db(
            session_factory,
            caja_id=caja_cerrada,
            tipo="ingreso",
            monto="15000.00",
            medio="efectivo",
            creado_por=admin.id,
        ),
        "gasto_efectivo": await insertar_movimiento_db(
            session_factory,
            caja_id=caja_cerrada,
            tipo="gasto",
            monto="3500.00",
            medio="efectivo",
            creado_por=admin.id,
        ),
        "deuda_efectivo": await insertar_movimiento_db(
            session_factory,
            caja_id=caja_cerrada,
            tipo="deuda",
            monto="12000.00",
            medio="efectivo",
            creado_por=admin.id,
        ),
        "ingreso_mp": await insertar_movimiento_db(
            session_factory,
            caja_id=caja_cerrada,
            tipo="ingreso",
            monto="8000.00",
            medio="mercadopago",
            creado_por=admin.id,
        ),
    }

    cobros: dict[str, uuid.UUID] = {}
    for nombre, medio, estado, monto in (
        ("efectivo_uno", "efectivo", "aprobado", "10000.00"),
        ("efectivo_dos", "efectivo", "aprobado", "5000.00"),
        ("mp_aprobado", "mercadopago", "aprobado", "8000.00"),
        ("mp_pendiente", "mercadopago", "pendiente", "3000.00"),
        ("efectivo_reembolsado", "efectivo", "reembolsado", "2000.00"),
        ("mp_rechazado", "mercadopago", "rechazado", "1000.00"),
        ("mp_perdido", "mercadopago", "perdido", "1200.00"),
    ):
        cobros[nombre] = await insertar_cobro_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_dos.id,
            tipo="otro",
            medio=medio,
            estado=estado,
            monto=monto,
            creado_por=admin.id,
            fecha_operacion=FECHA_CAJA_CERRADA,
        )

    os_demo_id = await _obra_social_id(session_factory, "OS Demo")
    os_otra_id = await insertar_obra_social(
        session_factory, consultorio_id, "OS Reportes Otra"
    )

    liquidacion_cerrada = await insertar_liquidacion_db(
        session_factory,
        consultorio_id=consultorio_id,
        obra_social_id=os_demo_id,
        creado_por=admin.id,
        desde=date(2026, 10, 20),
        hasta=date(2026, 11, 5),
        estado="cerrada",
        total_cobertura="60000.00",
        cantidad_practicas=3,
    )
    liquidacion_borrador = await insertar_liquidacion_db(
        session_factory,
        consultorio_id=consultorio_id,
        obra_social_id=os_demo_id,
        creado_por=admin.id,
        desde=date(2026, 11, 6),
        hasta=date(2026, 11, 30),
        estado="borrador",
        total_cobertura="20000.00",
        cantidad_practicas=1,
    )
    liquidacion_fuera = await insertar_liquidacion_db(
        session_factory,
        consultorio_id=consultorio_id,
        obra_social_id=os_otra_id,
        creado_por=admin.id,
        desde=date(2026, 12, 1),
        hasta=date(2026, 12, 31),
        estado="borrador",
        total_cobertura="999.00",
        cantidad_practicas=1,
    )

    prestaciones = await _prestaciones(session_factory)

    items = {}
    for nombre, liquidacion_id, codigo, cantidad, cobertura in (
        ("obt_cerrada_uno", liquidacion_cerrada, "OBT", 1, "20000.00"),
        ("obt_cerrada_dos", liquidacion_cerrada, "OBT", 1, "20000.00"),
        ("cons_cerrada", liquidacion_cerrada, "CONS", 1, "20000.00"),
        ("obt_borrador", liquidacion_borrador, "OBT", 1, "20000.00"),
    ):
        items[nombre] = await insertar_item_liquidable(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_dos.id,
            profesional_id=profesional.id,
            creado_por=admin.id,
            prestacion_id=prestaciones[codigo],
            prestacion_codigo=codigo,
            liquidacion_id=liquidacion_id,
            cantidad=cantidad,
            cobertura=cobertura,
        )

    # Soft-deleted line: must never add to the settlement aggregate.
    items["baja"] = await insertar_item_liquidable(
        session_factory,
        consultorio_id=consultorio_id,
        paciente_id=paciente_dos.id,
        profesional_id=profesional.id,
        creado_por=admin.id,
        prestacion_id=prestaciones["OBT"],
        prestacion_codigo="OBT",
        liquidacion_id=liquidacion_cerrada,
        cantidad=5,
        cobertura="99999.00",
        eliminado=True,
    )

    return {
        **data,
        "profesional": profesional,
        "profesional_dos": profesional_dos,
        "sillon_a": sillon_a,
        "sillon_b": sillon_b,
        "paciente_uno": paciente_uno,
        "paciente_dos": paciente_dos,
        "turnos": turnos,
        "caja_cerrada": caja_cerrada,
        "caja_abierta": caja_abierta,
        "caja_fuera": caja_fuera,
        "movimientos": movimientos,
        "cobros": cobros,
        "obra_social_demo_id": os_demo_id,
        "liquidacion_cerrada": liquidacion_cerrada,
        "liquidacion_borrador": liquidacion_borrador,
        "liquidacion_fuera": liquidacion_fuera,
        "items": items,
        "prestaciones": prestaciones,
        "desde": FECHA_DESDE,
        "hasta": FECHA_HASTA,
        "desde_utc": DESDE_UTC,
        "hasta_utc": HASTA_UTC,
        "caja_desde": CAJA_DESDE,
        "caja_hasta": CAJA_HASTA,
    }


async def _obra_social_id(
    session_factory: async_sessionmaker[AsyncSession], nombre: str
) -> uuid.UUID:
    async with session_factory() as session:
        obra_social_id = await session.scalar(
            text(
                "SELECT id FROM obras_sociales "
                "WHERE nombre = :nombre AND deleted_at IS NULL"
            ),
            {"nombre": nombre},
        )
    assert obra_social_id is not None
    return obra_social_id


async def insertar_obra_social(
    session_factory: async_sessionmaker[AsyncSession],
    consultorio_id: uuid.UUID,
    nombre: str,
) -> uuid.UUID:
    obra_social_id = uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO obras_sociales "
                "(id, consultorio_id, nombre, reglas_cobertura) "
                "VALUES (:id, :consultorio_id, :nombre, '{}'::jsonb)"
            ),
            {
                "id": obra_social_id,
                "consultorio_id": consultorio_id,
                "nombre": nombre,
            },
        )
    return obra_social_id


async def _prestaciones(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, uuid.UUID]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT codigo, id FROM prestaciones "
                    "WHERE deleted_at IS NULL"
                )
            )
        ).all()
    return {codigo: identificador for codigo, identificador in rows}


async def insertar_item_liquidable(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    consultorio_id: uuid.UUID,
    paciente_id: uuid.UUID,
    profesional_id: uuid.UUID,
    creado_por: uuid.UUID,
    prestacion_id: uuid.UUID,
    prestacion_codigo: str,
    liquidacion_id: uuid.UUID,
    cantidad: int = 1,
    cobertura: str = "20000.00",
    eliminado: bool = False,
) -> dict[str, uuid.UUID]:
    """Budget line plus payment plus its settlement line (one per concept)."""
    cobertura_decimal = Decimal(cobertura)
    precio_unitario = cobertura_decimal / cantidad
    subtotal = cobertura_decimal
    presupuesto_id = await insertar_presupuesto_db(
        session_factory,
        consultorio_id=consultorio_id,
        paciente_id=paciente_id,
        profesional_id=profesional_id,
        creado_por=creado_por,
        estado="finalizado",
        subtotal=f"{subtotal:.2f}",
        cobertura_calculada=f"{subtotal:.2f}",
        copago="0.00",
    )
    item_presupuesto_id = await insertar_item_db(
        session_factory,
        presupuesto_id=presupuesto_id,
        prestacion_id=prestacion_id,
        cantidad=cantidad,
        precio_unitario=f"{precio_unitario:.2f}",
        cobertura_item=f"{cobertura_decimal:.2f}",
        copago_item="0.00",
    )
    cobro_id = await insertar_cobro_db(
        session_factory,
        consultorio_id=consultorio_id,
        paciente_id=paciente_id,
        tipo="tratamiento",
        medio="efectivo",
        estado="aprobado",
        monto=f"{subtotal:.2f}",
        presupuesto_id=presupuesto_id,
        creado_por=creado_por,
        fecha_operacion=FECHA_COBRO_LIQUIDACION,
    )
    item_liquidacion_id = await insertar_item_liquidacion_db(
        session_factory,
        liquidacion_id=liquidacion_id,
        item_presupuesto_id=item_presupuesto_id,
        presupuesto_id=presupuesto_id,
        cobro_id=cobro_id,
        prestacion_id=prestacion_id,
        prestacion_codigo=prestacion_codigo,
        cantidad=cantidad,
        cobertura_item=f"{cobertura_decimal:.2f}",
    )
    if eliminado:
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "UPDATE items_liquidacion "
                    "SET is_active = false, deleted_at = now() "
                    "WHERE id = :id"
                ),
                {"id": item_liquidacion_id},
            )
    return {
        "presupuesto_id": presupuesto_id,
        "item_presupuesto_id": item_presupuesto_id,
        "cobro_id": cobro_id,
        "item_liquidacion_id": item_liquidacion_id,
    }


async def insertar_exportacion_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    consultorio_id: uuid.UUID,
    solicitado_por: uuid.UUID,
    alcance: str = "consultorio",
    paciente_id: uuid.UUID | None = None,
    estado: str = "pendiente",
    contenido: bytes | None = None,
    tamano_bytes: int | None = None,
    generada_at: datetime | None = None,
    intentos: int = 0,
    proximo_intento: datetime | None = None,
    ultimo_error: str | None = None,
    claim_token: uuid.UUID | None = None,
    reclamado_at: datetime | None = None,
    exportacion_id: uuid.UUID | None = None,
    completar: bool = True,
) -> uuid.UUID:
    """Insert one exportation, defaulting the fields each state requires."""
    if estado == "lista" and completar:
        contenido = contenido if contenido is not None else b"PK-fake-zip"
        tamano_bytes = tamano_bytes if tamano_bytes is not None else len(
            contenido
        )
        generada_at = generada_at or datetime.now(timezone.utc)
    if estado == "fallida" and ultimo_error is None and completar:
        ultimo_error = "limite_excedido:turnos"

    exportacion_id = exportacion_id or uuid.uuid4()
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO exportaciones "
                "(id, consultorio_id, solicitado_por, alcance, paciente_id, "
                "estado, contenido, tamano_bytes, generada_at, intentos, "
                "proximo_intento, ultimo_error, claim_token, reclamado_at) "
                "VALUES (:id, :consultorio_id, :solicitado_por, :alcance, "
                ":paciente_id, :estado, :contenido, :tamano_bytes, "
                ":generada_at, :intentos, :proximo_intento, :ultimo_error, "
                ":claim_token, :reclamado_at)"
            ),
            {
                "id": exportacion_id,
                "consultorio_id": consultorio_id,
                "solicitado_por": solicitado_por,
                "alcance": alcance,
                "paciente_id": paciente_id,
                "estado": estado,
                "contenido": contenido,
                "tamano_bytes": tamano_bytes,
                "generada_at": generada_at,
                "intentos": intentos,
                "proximo_intento": proximo_intento,
                "ultimo_error": ultimo_error,
                "claim_token": claim_token,
                "reclamado_at": reclamado_at,
            },
        )
    return exportacion_id


async def setup_agenda_reporte(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    con_sobreturno: bool = False,
) -> dict[str, object]:
    """Five appointments on Monday 9 November: 3 attended, 1 cancelled, 1 absent.

    Professional one has 480 available minutes (08:00-16:00) and 240 occupied
    minutes (three 80-minute attended appointments), i.e. exactly 50.00 %.
    Professional two has 240 available minutes and one absent appointment.
    """
    data = await setup_base(session_factory)
    consultorio_id = data["consultorio_id"]
    actores = data["actores"]

    profesional = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-REP-AG-1",
        usuario_id=actores["odontologo"].id,
        dias_atencion=(0, 1, 2, 3, 4),
        hora_desde=time(8, 0),
        hora_hasta=time(16, 0),
    )
    profesional_dos = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-REP-AG-2",
        dias_atencion=(0, 1, 2, 3, 4),
        hora_desde=time(8, 0),
        hora_hasta=time(12, 0),
    )
    sillon_a = await create_sillon(
        session_factory, consultorio_id, "Sillón Agenda A"
    )
    sillon_b = await create_sillon(
        session_factory, consultorio_id, "Sillón Agenda B"
    )
    paciente_uno = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Agenda",
        apellido="Uno",
        dni="42666101",
        telefono="+5491177771001",
    )
    paciente_dos = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Agenda",
        apellido="Dos",
        dni="42666102",
        telefono="+5491177771002",
    )

    inicio = datetime(2026, 11, 9, 8, 0, tzinfo=ARGENTINA_OFFSET)

    async def turno(
        *,
        inicio_turno: datetime,
        minutos: int,
        estado: str,
        profesional_id: uuid.UUID,
        sillon_id: uuid.UUID,
        paciente_id: uuid.UUID,
        sobreturno: bool = False,
    ) -> uuid.UUID:
        return await insertar_turno_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente_id,
            profesional_id=profesional_id,
            sillon_id=sillon_id,
            inicio=inicio_turno,
            fin=inicio_turno + timedelta(minutes=minutos),
            estado=estado,
            es_sobreturno=sobreturno,
        )

    turnos = {
        "atendido_uno": await turno(
            inicio_turno=inicio,
            minutos=80,
            estado="atendido",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_uno.id,
        ),
        "atendido_dos": await turno(
            inicio_turno=inicio + timedelta(minutes=80),
            minutos=80,
            estado="atendido",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_uno.id,
        ),
        "atendido_tres": await turno(
            inicio_turno=inicio + timedelta(minutes=160),
            minutos=80,
            estado="atendido",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_uno.id,
        ),
        "cancelado": await turno(
            inicio_turno=inicio + timedelta(hours=4),
            minutos=60,
            estado="cancelado",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_dos.id,
        ),
        "ausente": await turno(
            inicio_turno=datetime(
                2026, 11, 9, 9, 0, tzinfo=ARGENTINA_OFFSET
            ),
            minutos=60,
            estado="ausente",
            profesional_id=profesional_dos.id,
            sillon_id=sillon_b.id,
            paciente_id=paciente_dos.id,
        ),
        "local_2330": await turno(
            inicio_turno=datetime(
                2026, 11, 5, 2, 30, tzinfo=timezone.utc
            ),
            minutos=60,
            estado="atendido",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_uno.id,
        ),
    }
    if con_sobreturno:
        turnos["sobreturno"] = await turno(
            inicio_turno=datetime(
                2026, 11, 9, 8, 0, tzinfo=ARGENTINA_OFFSET
            ),
            minutos=120,
            estado="atendido",
            profesional_id=profesional.id,
            sillon_id=sillon_a.id,
            paciente_id=paciente_dos.id,
            sobreturno=True,
        )
    return {
        **data,
        "profesional": profesional,
        "profesional_dos": profesional_dos,
        "sillon_a": sillon_a,
        "sillon_b": sillon_b,
        "paciente_uno": paciente_uno,
        "paciente_dos": paciente_dos,
        "turnos": turnos,
        "desde": date(2026, 11, 9),
        "hasta": date(2026, 11, 9),
    }


async def setup_ausentismo_reporte(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """6 attended + 2 cancelled + 2 absent + 5 active, split by professional."""
    data = await setup_base(session_factory)
    consultorio_id = data["consultorio_id"]
    actores = data["actores"]

    profesional = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-REP-AU-1",
        usuario_id=actores["odontologo"].id,
        dias_atencion=(0, 1, 2, 3, 4),
        hora_desde=time(8, 0),
        hora_hasta=time(20, 0),
    )
    profesional_dos = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-REP-AU-2",
        dias_atencion=(0, 1, 2, 3, 4),
        hora_desde=time(8, 0),
        hora_hasta=time(20, 0),
    )
    sillon_a = await create_sillon(
        session_factory, consultorio_id, "Sillón Ausentismo A"
    )
    sillon_b = await create_sillon(
        session_factory, consultorio_id, "Sillón Ausentismo B"
    )
    paciente = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Ausentismo",
        apellido="Demo",
        dni="42666201",
        telefono="+5491177771101",
    )
    fecha = datetime(2026, 11, 9, 8, 0, tzinfo=ARGENTINA_OFFSET)

    async def turno(
        profesional_id: uuid.UUID,
        sillon_id: uuid.UUID,
        hora: int,
        estado: str,
    ) -> uuid.UUID:
        inicio = fecha + timedelta(hours=hora - 8)
        return await insertar_turno_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            profesional_id=profesional_id,
            sillon_id=sillon_id,
            inicio=inicio,
            fin=inicio + timedelta(hours=1),
            estado=estado,
        )

    turnos: dict[str, uuid.UUID] = {}
    for indice, hora in enumerate((8, 9, 10)):
        turnos[f"p1_atendido_{indice}"] = await turno(
            profesional.id, sillon_a.id, hora, "atendido"
        )
    turnos["p1_cancelado"] = await turno(
        profesional.id, sillon_a.id, 11, "cancelado"
    )
    turnos["p1_ausente"] = await turno(
        profesional.id, sillon_a.id, 12, "ausente"
    )
    for indice, hora in enumerate((13, 14, 15)):
        turnos[f"p1_activo_{indice}"] = await turno(
            profesional.id,
            sillon_a.id,
            hora,
            ("reservado", "confirmado", "en_sala")[indice],
        )

    for indice, hora in enumerate((8, 9, 10)):
        turnos[f"p2_atendido_{indice}"] = await turno(
            profesional_dos.id, sillon_b.id, hora, "atendido"
        )
    turnos["p2_cancelado"] = await turno(
        profesional_dos.id, sillon_b.id, 11, "cancelado"
    )
    turnos["p2_ausente"] = await turno(
        profesional_dos.id, sillon_b.id, 12, "ausente"
    )
    turnos["p2_activo_0"] = await turno(
        profesional_dos.id, sillon_b.id, 13, "reservado"
    )
    turnos["p2_activo_1"] = await turno(
        profesional_dos.id, sillon_b.id, 14, "confirmado"
    )

    return {
        **data,
        "profesional": profesional,
        "profesional_dos": profesional_dos,
        "sillon_a": sillon_a,
        "sillon_b": sillon_b,
        "paciente": paciente,
        "turnos": turnos,
        "desde": date(2026, 11, 9),
        "hasta": date(2026, 11, 9),
    }


async def setup_liquidaciones_reporte(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Closed 60000/3 (OBT×2 + CONS) and draft 20000/1 (LIM) of OS Demo."""
    data = await setup_base(session_factory)
    consultorio_id = data["consultorio_id"]
    admin = data["actores"]["administrador"]
    odontologo = data["actores"]["odontologo"]

    profesional = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-REP-LIQ-1",
        usuario_id=odontologo.id,
    )
    paciente = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Liquidación",
        apellido="Demo",
        dni="42666301",
        telefono="+5491177771201",
    )
    prestaciones = await _prestaciones(session_factory)
    os_demo_id = await _obra_social_id(session_factory, "OS Demo")

    cerrada = await insertar_liquidacion_db(
        session_factory,
        consultorio_id=consultorio_id,
        obra_social_id=os_demo_id,
        creado_por=admin.id,
        desde=date(2026, 10, 20),
        hasta=date(2026, 11, 5),
        estado="cerrada",
        total_cobertura="60000.00",
        cantidad_practicas=3,
    )
    borrador = await insertar_liquidacion_db(
        session_factory,
        consultorio_id=consultorio_id,
        obra_social_id=os_demo_id,
        creado_por=admin.id,
        desde=date(2026, 11, 6),
        hasta=date(2026, 11, 30),
        estado="borrador",
        total_cobertura="20000.00",
        cantidad_practicas=1,
    )

    items = {}
    for nombre, liquidacion_id, codigo, cobertura in (
        ("obt_uno", cerrada, "OBT", "20000.00"),
        ("obt_dos", cerrada, "OBT", "20000.00"),
        ("cons", cerrada, "CONS", "20000.00"),
        ("lim_borrador", borrador, "LIM", "20000.00"),
    ):
        items[nombre] = await insertar_item_liquidable(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            profesional_id=profesional.id,
            creado_por=admin.id,
            prestacion_id=prestaciones[codigo],
            prestacion_codigo=codigo,
            liquidacion_id=liquidacion_id,
            cantidad=1,
            cobertura=cobertura,
        )
    items["baja"] = await insertar_item_liquidable(
        session_factory,
        consultorio_id=consultorio_id,
        paciente_id=paciente.id,
        profesional_id=profesional.id,
        creado_por=admin.id,
        prestacion_id=prestaciones["OBT"],
        prestacion_codigo="OBT",
        liquidacion_id=cerrada,
        cantidad=5,
        cobertura="99999.00",
        eliminado=True,
    )

    tenant = await otro_consultorio(session_factory)
    os_ajena_id = await insertar_obra_social(
        session_factory, tenant["consultorio_id"], "OS Ajena C15"
    )

    return {
        **data,
        "profesional": profesional,
        "paciente": paciente,
        "prestaciones": prestaciones,
        "obra_social_demo_id": os_demo_id,
        "obra_social_ajena_id": os_ajena_id,
        "liquidacion_cerrada": cerrada,
        "liquidacion_borrador": borrador,
        "items": items,
        "desde": date(2026, 11, 1),
        "hasta": date(2026, 11, 30),
    }


async def setup_bordes_reporte(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """1200 attended appointments over 60 days for one professional/chair."""
    data = await setup_base(session_factory)
    consultorio_id = data["consultorio_id"]
    actores = data["actores"]
    profesional = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-REP-BOR-1",
        usuario_id=actores["odontologo"].id,
        duracion_base_min=30,
        dias_atencion=(0, 1, 2, 3, 4, 5, 6),
        hora_desde=time(8, 0),
        hora_hasta=time(20, 0),
    )
    sillon = await create_sillon(
        session_factory, consultorio_id, "Sillón Bordes"
    )
    paciente = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Bordes",
        apellido="Demo",
        dni="42666401",
        telefono="+5491177771301",
    )
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO turnos "
                "(id, consultorio_id, paciente_id, profesional_id, "
                "sillon_id, inicio, fin, estado, origen, sena_estado) "
                "SELECT gen_random_uuid(), :consultorio_id, :paciente_id, "
                ":profesional_id, :sillon_id, inicio, "
                "inicio + interval '30 minutes', 'atendido', "
                "'recepcion', 'no_requiere' "
                "FROM ("
                "SELECT (DATE '2026-01-01' "
                "+ ((n / 20) * interval '1 day') "
                "+ interval '8 hours' "
                "+ ((n % 20) * interval '30 minutes')) "
                "AT TIME ZONE 'America/Argentina/Buenos_Aires' AS inicio "
                "FROM generate_series(0, 1199) AS g(n)"
                ") AS agenda"
            ),
            {
                "consultorio_id": consultorio_id,
                "paciente_id": paciente.id,
                "profesional_id": profesional.id,
                "sillon_id": sillon.id,
            },
        )
    return {
        **data,
        "profesional": profesional,
        "sillon": sillon,
        "paciente": paciente,
        "desde": date(2026, 1, 1),
        "hasta": date(2026, 3, 1),
        "total": 1200,
    }


async def setup_orden_reporte(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Two appointments sharing `inicio` to prove the stable `inicio, id` order."""
    data = await setup_base(session_factory)
    consultorio_id = data["consultorio_id"]
    actores = data["actores"]
    profesional = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-REP-ORD-1",
        usuario_id=actores["odontologo"].id,
    )
    profesional_dos = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-REP-ORD-2",
    )
    sillon_a = await create_sillon(
        session_factory, consultorio_id, "Sillón Orden A"
    )
    sillon_b = await create_sillon(
        session_factory, consultorio_id, "Sillón Orden B"
    )
    paciente = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="Orden",
        apellido="Demo",
        dni="42666501",
        telefono="+5491177771401",
    )
    inicio = datetime(2026, 11, 9, 9, 0, tzinfo=ARGENTINA_OFFSET)
    turnos = []
    for profesional_id, sillon_id in (
        (profesional.id, sillon_a.id),
        (profesional_dos.id, sillon_b.id),
    ):
        turnos.append(
            await insertar_turno_db(
                session_factory,
                consultorio_id=consultorio_id,
                paciente_id=paciente.id,
                profesional_id=profesional_id,
                sillon_id=sillon_id,
                inicio=inicio,
                fin=inicio + timedelta(hours=1),
                estado="atendido",
            )
        )
    return {
        **data,
        "profesional": profesional,
        "profesional_dos": profesional_dos,
        "sillon_a": sillon_a,
        "sillon_b": sillon_b,
        "paciente": paciente,
        "turnos": turnos,
        "desde": date(2026, 11, 9),
        "hasta": date(2026, 11, 9),
    }


async def setup_rbac_reporte(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, object]:
    """Two professionals with one appointment and one payment each.

    The payments are the evidence that the dentist's cash report is scoped to
    their own budget: admin sees 3000.00, the linked dentist only 1000.00.
    """
    data = await setup_base(session_factory)
    consultorio_id = data["consultorio_id"]
    actores = data["actores"]
    admin = actores["administrador"]
    odontologo = actores["odontologo"]

    profesional = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-REP-RBAC-1",
        usuario_id=odontologo.id,
    )
    profesional_dos = await create_profesional(
        session_factory,
        consultorio_id,
        "MP-REP-RBAC-2",
    )
    sillon_a = await create_sillon(
        session_factory, consultorio_id, "Sillón RBAC A"
    )
    sillon_b = await create_sillon(
        session_factory, consultorio_id, "Sillón RBAC B"
    )
    paciente = await create_paciente(
        session_factory,
        consultorio_id,
        nombre="RBAC",
        apellido="Demo",
        dni="42666601",
        telefono="+5491177771501",
    )
    inicio = datetime(2026, 11, 9, 9, 0, tzinfo=ARGENTINA_OFFSET)
    turnos = {}
    for nombre, profesional_id, sillon_id in (
        ("propio", profesional.id, sillon_a.id),
        ("ajeno", profesional_dos.id, sillon_b.id),
    ):
        turnos[nombre] = await insertar_turno_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            profesional_id=profesional_id,
            sillon_id=sillon_id,
            inicio=inicio,
            fin=inicio + timedelta(hours=1),
            estado="atendido",
        )

    cobros = {}
    for nombre, profesional_id, monto in (
        ("propio", profesional.id, "1000.00"),
        ("ajeno", profesional_dos.id, "2000.00"),
    ):
        presupuesto_id = await insertar_presupuesto_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            profesional_id=profesional_id,
            creado_por=admin.id,
            estado="finalizado",
            subtotal=monto,
            cobertura_calculada="0.00",
            copago=monto,
        )
        cobros[nombre] = await insertar_cobro_db(
            session_factory,
            consultorio_id=consultorio_id,
            paciente_id=paciente.id,
            tipo="tratamiento",
            medio="efectivo",
            estado="aprobado",
            monto=monto,
            presupuesto_id=presupuesto_id,
            creado_por=admin.id,
            fecha_operacion=date(2026, 11, 4),
        )
    return {
        **data,
        "profesional": profesional,
        "profesional_dos": profesional_dos,
        "sillon_a": sillon_a,
        "sillon_b": sillon_b,
        "paciente": paciente,
        "turnos": turnos,
        "cobros": cobros,
        "desde": date(2026, 11, 9),
        "hasta": date(2026, 11, 9),
        "caja_desde": date(2026, 11, 1),
        "caja_hasta": date(2026, 11, 30),
    }
