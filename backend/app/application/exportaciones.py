"""Exportation use cases: request, generation, retries and Redis sweep (C-15).

The row in PostgreSQL is the job (D3): the POST only persists it and tries to
enqueue a best-effort Redis message. The worker claims the row with a token,
collects every entity in a read transaction, builds the ZIP outside the claim
transaction and persists it only while the claim is still valid. A failure
before the attempt ceiling goes back to `pendiente` with exponential backoff;
the ceiling leaves it `fallida` with the reason. Redis being down never loses a
job because `list_pendientes_vencidos` sweeps the table.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application.clinica import auditar
from app.core.queues import REPORTES_GENERAR, get_redis_client, try_enqueue
from app.core.settings import Settings
from app.domain.agenda import ARGENTINA_OFFSET
from app.domain.exportacion import (
    CAMPOS_EXCLUIDOS,
    ENTIDADES_EXPORTABLES,
    AdjuntoExportado,
    nombre_adjunto,
)
from app.domain.reportes import proximo_intento_con_backoff
from app.infrastructure.exportacion import construir_zip
from app.infrastructure.uow import UnitOfWork
from app.models import (
    Adjunto,
    CajaDiaria,
    Cobro,
    Comprobante,
    ComprobanteEnvio,
    Consentimiento,
    Consultorio,
    EntradaListaEspera,
    Evolucion,
    Exportacion,
    HallazgoDental,
    HistoriaClinica,
    ItemLiquidacion,
    ItemPresupuesto,
    LiquidacionObraSocial,
    MensajeWhatsApp,
    MovimientoCaja,
    ObraSocial,
    Odontograma,
    Paciente,
    Prestacion,
    Presupuesto,
    Recordatorio,
    RegistroAuditoria,
    Turno,
    Usuario,
)

ESTADOS_TURNO: tuple[str, ...] = (
    "reservado",
    "confirmado",
    "en_sala",
    "atendido",
    "cancelado",
    "ausente",
)


@dataclass(frozen=True)
class ConfiguracionExportacion:
    """Limits and worker cadence, loaded from Settings (D11/D13)."""

    max_filas: int = 50000
    max_bytes: int = 67108864
    max_intentos: int = 3
    claim_timeout_seconds: int = 300


class LimiteExportacion(Exception):
    """Permanent failure: an entity row cap or the ZIP byte cap was exceeded."""


def configuracion_exportacion(settings: Settings) -> ConfiguracionExportacion:
    return ConfiguracionExportacion(
        max_filas=settings.exportacion_max_filas,
        max_bytes=settings.exportacion_max_bytes,
        max_intentos=settings.exportacion_max_intentos,
        claim_timeout_seconds=settings.exportacion_claim_timeout_seconds,
    )


def _roles(usuario: Usuario) -> set[str]:
    return {
        rol.nombre
        for rol in usuario.roles
        if rol.is_active and rol.deleted_at is None
    }


def _no_encontrado(detalle: str):
    from fastapi import HTTPException, status

    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detalle)


def _prohibido():
    from fastapi import HTTPException, status

    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permisos insuficientes",
    )


def _conflicto(detalle: str):
    from fastapi import HTTPException, status

    return HTTPException(
        status_code=status.HTTP_409_CONFLICT, detail=detalle
    )


def _json_value(valor: object) -> object:
    if isinstance(valor, uuid.UUID):
        return str(valor)
    if isinstance(valor, datetime):
        momento = valor
        if momento.tzinfo is None:
            momento = momento.replace(tzinfo=timezone.utc)
        return momento.astimezone(ARGENTINA_OFFSET).isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, dict):
        return {
            str(clave): _json_value(contenido)
            for clave, contenido in valor.items()
        }
    if isinstance(valor, list):
        return [_json_value(contenido) for contenido in valor]
    return valor


def _excluidos(entidad: str, columnas: Sequence[str]) -> set[str]:
    if entidad == "usuarios":
        return set(columnas) - {"id", "nombre", "email", "roles"}
    prefijo = f"{entidad}."
    return {
        campo.split(".", 1)[1]
        for campo in CAMPOS_EXCLUIDOS
        if campo.startswith(prefijo)
    }


MODELOS: dict[str, type] = {
    "pacientes": Paciente,
    "obras_sociales": ObraSocial,
    "turnos": Turno,
    "historias_clinicas": HistoriaClinica,
    "evoluciones": Evolucion,
    "odontogramas": Odontograma,
    "hallazgos_dentales": HallazgoDental,
    "adjuntos": Adjunto,
    "consentimientos": Consentimiento,
    "presupuestos": Presupuesto,
    "items_presupuesto": ItemPresupuesto,
    "prestaciones": Prestacion,
    "cobros": Cobro,
    "cajas_diarias": CajaDiaria,
    "movimientos_caja": MovimientoCaja,
    "comprobantes": Comprobante,
    "comprobantes_envios": ComprobanteEnvio,
    "liquidaciones_obras_sociales": LiquidacionObraSocial,
    "items_liquidacion": ItemLiquidacion,
    "recordatorios": Recordatorio,
    "mensajes_whatsapp": MensajeWhatsApp,
    "entradas_lista_espera": EntradaListaEspera,
    "registro_auditoria": RegistroAuditoria,
    "usuarios": Usuario,
}


def _columnas(entidad: str) -> list[str]:
    modelo = MODELOS[entidad]
    columnas = [columna.name for columna in modelo.__table__.columns]
    excluidas = _excluidos(entidad, columnas)
    if entidad == "usuarios":
        return ["id", "nombre", "email", "roles"]
    return [columna for columna in columnas if columna not in excluidas]


def _serializar(entidad: str, fila: object) -> dict[str, object]:
    if entidad == "usuarios":
        return {
            "id": str(fila.id),
            "nombre": fila.nombre,
            "email": fila.email,
            "roles": sorted(
                rol.nombre
                for rol in fila.roles
                if rol.is_active and rol.deleted_at is None
            ),
        }
    return {
        columna: _json_value(getattr(fila, columna))
        for columna in _columnas(entidad)
    }


async def _filas(
    session: AsyncSession,
    modelo: type,
    condiciones: list,
    *,
    orden: tuple | None = None,
) -> list:
    statement = select(modelo).where(*condiciones)
    statement = statement.order_by(*(orden or (modelo.id,)))
    return list(await session.scalars(statement))


@dataclass(frozen=True)
class DatosExportacion:
    consultorio: dict[str, object]
    entidades: dict[str, list[dict[str, object]]]
    columnas: dict[str, list[str]]
    adjuntos: list[AdjuntoExportado]


async def _recolectar(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    alcance: str,
    paciente_id: uuid.UUID | None,
    max_filas: int,
) -> DatosExportacion:
    session = uow.session
    consultorio = await uow.consultorios.get(consultorio_id)
    if consultorio is None:  # pragma: no cover - FK guarantees it
        raise ValueError("Consultorio inexistente")
    paciente = (
        await uow.pacientes.get(paciente_id)
        if alcance == "paciente" and paciente_id is not None
        else None
    )

    def activo(modelo: type):
        return [modelo.deleted_at.is_(None), modelo.consultorio_id == consultorio_id]

    if alcance == "consultorio":
        pacientes = await _filas(
            session,
            Paciente,
            activo(Paciente),
            orden=(Paciente.apellido, Paciente.nombre, Paciente.id),
        )
        obras = await _filas(
            session,
            ObraSocial,
            activo(ObraSocial),
            orden=(ObraSocial.nombre, ObraSocial.id),
        )
        turnos = await _filas(
            session, Turno, activo(Turno), orden=(Turno.inicio, Turno.id)
        )
        turno_ids = [turno.id for turno in turnos]
        historias = await _filas(
            session,
            HistoriaClinica,
            activo(HistoriaClinica),
            orden=(HistoriaClinica.fecha_apertura, HistoriaClinica.id),
        )
        historia_ids = [historia.id for historia in historias]
        evoluciones = await _filas(
            session,
            Evolucion,
            [Evolucion.deleted_at.is_(None), Evolucion.historia_id.in_(historia_ids)]
            if historia_ids
            else [Evolucion.id.is_(None)],
            orden=(Evolucion.fecha, Evolucion.id),
        )
        odontogramas = await _filas(
            session,
            Odontograma,
            [Odontograma.historia_id.in_(historia_ids)]
            if historia_ids
            else [Odontograma.id.is_(None)],
            orden=(Odontograma.version, Odontograma.id),
        )
        odontograma_ids = [odontograma.id for odontograma in odontogramas]
        hallazgos = await _filas(
            session,
            HallazgoDental,
            [HallazgoDental.odontograma_id.in_(odontograma_ids)]
            if odontograma_ids
            else [HallazgoDental.id.is_(None)],
            orden=(HallazgoDental.pieza, HallazgoDental.cara, HallazgoDental.id),
        )
        adjuntos_orm = await _filas(
            session,
            Adjunto,
            [Adjunto.deleted_at.is_(None), Adjunto.historia_id.in_(historia_ids)]
            if historia_ids
            else [Adjunto.id.is_(None)],
            orden=(Adjunto.created_at, Adjunto.id),
        )
        consentimientos = await _filas(
            session,
            Consentimiento,
            activo(Consentimiento),
            orden=(Consentimiento.fecha, Consentimiento.id),
        )
        presupuestos = await _filas(
            session,
            Presupuesto,
            activo(Presupuesto),
            orden=(Presupuesto.created_at, Presupuesto.id),
        )
        presupuesto_ids = [
            presupuesto.id for presupuesto in presupuestos
        ]
        items_presupuesto = await _filas(
            session,
            ItemPresupuesto,
            [
                ItemPresupuesto.deleted_at.is_(None),
                ItemPresupuesto.presupuesto_id.in_(presupuesto_ids),
            ]
            if presupuesto_ids
            else [ItemPresupuesto.id.is_(None)],
            orden=(ItemPresupuesto.created_at, ItemPresupuesto.id),
        )
        prestaciones = await _filas(
            session,
            Prestacion,
            [Prestacion.deleted_at.is_(None)],
            orden=(Prestacion.codigo, Prestacion.id),
        )
        cobros = await _filas(
            session, Cobro, activo(Cobro), orden=(Cobro.fecha_operacion, Cobro.id)
        )
        cajas = await _filas(
            session,
            CajaDiaria,
            activo(CajaDiaria),
            orden=(CajaDiaria.fecha, CajaDiaria.id),
        )
        caja_ids = [caja.id for caja in cajas]
        movimientos = await _filas(
            session,
            MovimientoCaja,
            [
                MovimientoCaja.deleted_at.is_(None),
                MovimientoCaja.caja_id.in_(caja_ids),
            ]
            if caja_ids
            else [MovimientoCaja.id.is_(None)],
            orden=(MovimientoCaja.created_at, MovimientoCaja.id),
        )
        comprobantes = await _filas(
            session,
            Comprobante,
            activo(Comprobante),
            orden=(Comprobante.fecha_emision, Comprobante.id),
        )
        comprobante_ids = [
            comprobante.id for comprobante in comprobantes
        ]
        envios = await _filas(
            session,
            ComprobanteEnvio,
            [
                ComprobanteEnvio.deleted_at.is_(None),
                ComprobanteEnvio.comprobante_id.in_(comprobante_ids),
            ]
            if comprobante_ids
            else [ComprobanteEnvio.id.is_(None)],
            orden=(ComprobanteEnvio.created_at, ComprobanteEnvio.id),
        )
        liquidaciones = await _filas(
            session,
            LiquidacionObraSocial,
            activo(LiquidacionObraSocial),
            orden=(LiquidacionObraSocial.desde, LiquidacionObraSocial.id),
        )
        liquidacion_ids = [
            liquidacion.id for liquidacion in liquidaciones
        ]
        items_liquidacion = await _filas(
            session,
            ItemLiquidacion,
            [
                ItemLiquidacion.deleted_at.is_(None),
                ItemLiquidacion.liquidacion_id.in_(liquidacion_ids),
            ]
            if liquidacion_ids
            else [ItemLiquidacion.id.is_(None)],
            orden=(ItemLiquidacion.created_at, ItemLiquidacion.id),
        )
        recordatorios = await _filas(
            session,
            Recordatorio,
            [Recordatorio.turno_id.in_(turno_ids)]
            if turno_ids
            else [Recordatorio.id.is_(None)],
            orden=(Recordatorio.programado_para, Recordatorio.id),
        )
        entradas = await _filas(
            session,
            EntradaListaEspera,
            activo(EntradaListaEspera),
            orden=(EntradaListaEspera.orden, EntradaListaEspera.id),
        )
        entrada_ids = [entrada.id for entrada in entradas]
        mensajes = await _filas(
            session,
            MensajeWhatsApp,
            [
                or_(
                    MensajeWhatsApp.turno_id.in_(turno_ids),
                    MensajeWhatsApp.lista_espera_id.in_(entrada_ids),
                )
            ]
            if turno_ids or entrada_ids
            else [MensajeWhatsApp.id.is_(None)],
            orden=(MensajeWhatsApp.created_at, MensajeWhatsApp.id),
        )
        usuarios = await _filas(
            session,
            Usuario,
            [Usuario.deleted_at.is_(None)],
            orden=(Usuario.nombre, Usuario.id),
        )
        ids_auditoria = {
            str(fila.id)
            for coleccion in (
                pacientes,
                obras,
                turnos,
                historias,
                evoluciones,
                odontogramas,
                hallazgos,
                adjuntos_orm,
                consentimientos,
                presupuestos,
                items_presupuesto,
                prestaciones,
                cobros,
                cajas,
                movimientos,
                comprobantes,
                envios,
                liquidaciones,
                items_liquidacion,
                recordatorios,
                mensajes,
                entradas,
                usuarios,
            )
            for fila in coleccion
        }
        auditoria = await _filas(
            session,
            RegistroAuditoria,
            [RegistroAuditoria.entidad_id.in_(ids_auditoria)],
            orden=(RegistroAuditoria.timestamp, RegistroAuditoria.id),
        )
    else:
        if paciente is None:
            pacientes = []
            obras = []
            turnos = []
            historias = []
            evoluciones = []
            odontogramas = []
            hallazgos = []
            adjuntos_orm = []
            consentimientos = []
            presupuestos = []
            items_presupuesto = []
            prestaciones = []
            cobros = []
            movimientos = []
            cajas = []
            comprobantes = []
            envios = []
            liquidaciones = []
            items_liquidacion = []
            recordatorios = []
            mensajes = []
            entradas = []
            auditoria = []
            usuarios = []
        else:
            pacientes = [paciente]
            obras = (
                [await uow.obras_sociales.get(paciente.obra_social_id)]
                if paciente.obra_social_id is not None
                else []
            )
            obras = [obra for obra in obras if obra is not None]
            turnos = await _filas(session, Turno, [Turno.deleted_at.is_(None), Turno.paciente_id == paciente.id], orden=(Turno.inicio, Turno.id))
            historias = await _filas(session, HistoriaClinica, [HistoriaClinica.deleted_at.is_(None), HistoriaClinica.paciente_id == paciente.id], orden=(HistoriaClinica.fecha_apertura, HistoriaClinica.id))
            historia_ids = [historia.id for historia in historias]
            evoluciones = await _filas(session, Evolucion, [Evolucion.deleted_at.is_(None), Evolucion.historia_id.in_(historia_ids)] if historia_ids else [Evolucion.id.is_(None)], orden=(Evolucion.fecha, Evolucion.id))
            odontogramas = await _filas(session, Odontograma, [Odontograma.historia_id.in_(historia_ids)] if historia_ids else [Odontograma.id.is_(None)], orden=(Odontograma.version, Odontograma.id))
            odontograma_ids = [odontograma.id for odontograma in odontogramas]
            hallazgos = await _filas(session, HallazgoDental, [HallazgoDental.odontograma_id.in_(odontograma_ids)] if odontograma_ids else [HallazgoDental.id.is_(None)], orden=(HallazgoDental.pieza, HallazgoDental.cara, HallazgoDental.id))
            adjuntos_orm = await _filas(session, Adjunto, [Adjunto.deleted_at.is_(None), Adjunto.historia_id.in_(historia_ids)] if historia_ids else [Adjunto.id.is_(None)], orden=(Adjunto.created_at, Adjunto.id))
            consentimientos = await _filas(session, Consentimiento, [Consentimiento.deleted_at.is_(None), Consentimiento.paciente_id == paciente.id], orden=(Consentimiento.fecha, Consentimiento.id))
            presupuestos = await _filas(session, Presupuesto, [Presupuesto.deleted_at.is_(None), Presupuesto.paciente_id == paciente.id], orden=(Presupuesto.created_at, Presupuesto.id))
            presupuesto_ids = [presupuesto.id for presupuesto in presupuestos]
            items_presupuesto = await _filas(session, ItemPresupuesto, [ItemPresupuesto.deleted_at.is_(None), ItemPresupuesto.presupuesto_id.in_(presupuesto_ids)] if presupuesto_ids else [ItemPresupuesto.id.is_(None)], orden=(ItemPresupuesto.created_at, ItemPresupuesto.id))
            prestacion_ids = {item.prestacion_id for item in items_presupuesto}
            prestacion_ids |= {turno.prestacion_id for turno in turnos if turno.prestacion_id is not None}
            prestaciones = await _filas(session, Prestacion, [Prestacion.id.in_(prestacion_ids)] if prestacion_ids else [Prestacion.id.is_(None)], orden=(Prestacion.codigo, Prestacion.id))
            cobros = await _filas(session, Cobro, [Cobro.deleted_at.is_(None), Cobro.paciente_id == paciente.id], orden=(Cobro.fecha_operacion, Cobro.id))
            cobro_ids = [cobro.id for cobro in cobros]
            movimientos = await _filas(session, MovimientoCaja, [MovimientoCaja.deleted_at.is_(None), MovimientoCaja.cobro_id.in_(cobro_ids)] if cobro_ids else [MovimientoCaja.id.is_(None)], orden=(MovimientoCaja.created_at, MovimientoCaja.id))
            caja_ids = {movimiento.caja_id for movimiento in movimientos}
            cajas = await _filas(session, CajaDiaria, [CajaDiaria.deleted_at.is_(None), CajaDiaria.id.in_(caja_ids)] if caja_ids else [CajaDiaria.id.is_(None)], orden=(CajaDiaria.fecha, CajaDiaria.id))
            comprobantes = await _filas(session, Comprobante, [Comprobante.deleted_at.is_(None), Comprobante.paciente_id == paciente.id], orden=(Comprobante.fecha_emision, Comprobante.id))
            comprobante_ids = [comprobante.id for comprobante in comprobantes]
            envios = await _filas(session, ComprobanteEnvio, [ComprobanteEnvio.deleted_at.is_(None), ComprobanteEnvio.comprobante_id.in_(comprobante_ids)] if comprobante_ids else [ComprobanteEnvio.id.is_(None)], orden=(ComprobanteEnvio.created_at, ComprobanteEnvio.id))
            items_liq_src = await _filas(session, ItemLiquidacion, [ItemLiquidacion.deleted_at.is_(None), ItemLiquidacion.presupuesto_id.in_(presupuesto_ids)] if presupuesto_ids else [ItemLiquidacion.id.is_(None)], orden=(ItemLiquidacion.created_at, ItemLiquidacion.id))
            liquidacion_ids = {item.liquidacion_id for item in items_liq_src}
            liquidaciones = await _filas(session, LiquidacionObraSocial, [LiquidacionObraSocial.deleted_at.is_(None), LiquidacionObraSocial.id.in_(liquidacion_ids)] if liquidacion_ids else [LiquidacionObraSocial.id.is_(None)], orden=(LiquidacionObraSocial.desde, LiquidacionObraSocial.id))
            items_liquidacion = [item for item in items_liq_src if item.liquidacion_id in liquidacion_ids]
            turno_ids = [turno.id for turno in turnos]
            recordatorios = await _filas(session, Recordatorio, [Recordatorio.turno_id.in_(turno_ids)] if turno_ids else [Recordatorio.id.is_(None)], orden=(Recordatorio.programado_para, Recordatorio.id))
            entradas = await _filas(session, EntradaListaEspera, [EntradaListaEspera.deleted_at.is_(None), EntradaListaEspera.paciente_id == paciente.id], orden=(EntradaListaEspera.orden, EntradaListaEspera.id))
            entrada_ids = [entrada.id for entrada in entradas]
            mensajes = await _filas(session, MensajeWhatsApp, [or_(MensajeWhatsApp.turno_id.in_(turno_ids), MensajeWhatsApp.lista_espera_id.in_(entrada_ids))] if turno_ids or entrada_ids else [MensajeWhatsApp.id.is_(None)], orden=(MensajeWhatsApp.created_at, MensajeWhatsApp.id))
            ids_auditoria = {str(paciente.id)}
            for coleccion in (
                historias,
                evoluciones,
                odontogramas,
                hallazgos,
                adjuntos_orm,
                consentimientos,
                presupuestos,
                items_presupuesto,
                turnos,
                cobros,
                movimientos,
                cajas,
                comprobantes,
                envios,
                liquidaciones,
                items_liquidacion,
                recordatorios,
                mensajes,
                entradas,
            ):
                ids_auditoria |= {str(fila.id) for fila in coleccion}
            auditoria = await _filas(session, RegistroAuditoria, [RegistroAuditoria.entidad_id.in_(ids_auditoria)], orden=(RegistroAuditoria.timestamp, RegistroAuditoria.id))
            usuarios = []

    crudas: dict[str, list] = {
        "pacientes": pacientes,
        "obras_sociales": obras,
        "turnos": turnos,
        "historias_clinicas": historias,
        "evoluciones": evoluciones,
        "odontogramas": odontogramas,
        "hallazgos_dentales": hallazgos,
        "adjuntos": adjuntos_orm,
        "consentimientos": consentimientos,
        "presupuestos": presupuestos,
        "items_presupuesto": items_presupuesto,
        "prestaciones": prestaciones,
        "cobros": cobros,
        "cajas_diarias": cajas,
        "movimientos_caja": movimientos,
        "comprobantes": comprobantes,
        "comprobantes_envios": envios,
        "liquidaciones_obras_sociales": liquidaciones,
        "items_liquidacion": items_liquidacion,
        "recordatorios": recordatorios,
        "mensajes_whatsapp": mensajes,
        "entradas_lista_espera": entradas,
        "registro_auditoria": auditoria,
        "usuarios": usuarios,
    }

    entidades: dict[str, list[dict[str, object]]] = {}
    for entidad in ENTIDADES_EXPORTABLES:
        filas = crudas[entidad]
        if len(filas) > max_filas:
            raise LimiteExportacion(f"limite_excedido:{entidad}")
        entidades[entidad] = [_serializar(entidad, fila) for fila in filas]

    return DatosExportacion(
        consultorio={
            "id": str(consultorio.id),
            "nombre": consultorio.nombre,
            "slug": consultorio.slug,
        },
        entidades=entidades,
        columnas={entidad: _columnas(entidad) for entidad in ENTIDADES_EXPORTABLES},
        adjuntos=[
            AdjuntoExportado(
                ruta=nombre_adjunto(adjunto.id, adjunto.nombre),
                contenido=adjunto.contenido,
            )
            for adjunto in adjuntos_orm
        ],
    )


async def generar_artefacto(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    exportacion_id: uuid.UUID,
    consultorio_id: uuid.UUID,
    alcance: str,
    paciente_id: uuid.UUID | None,
    config: ConfiguracionExportacion,
    generado_en: datetime,
) -> bytes:
    """Collect, build and enforce the byte limit outside the claim transaction."""
    async with UnitOfWork(session_factory) as uow:
        datos = await _recolectar(
            uow,
            consultorio_id=consultorio_id,
            alcance=alcance,
            paciente_id=paciente_id,
            max_filas=config.max_filas,
        )
        contenido = construir_zip(
            exportacion_id=exportacion_id,
            alcance=alcance,
            generado_en=generado_en,
            consultorio=datos.consultorio,
            entidades=datos.entidades,
            columnas=datos.columnas,
            adjuntos=datos.adjuntos,
        )
    if len(contenido) > config.max_bytes:
        raise LimiteExportacion("limite_excedido:tamano_bytes")
    return contenido


async def procesar_exportacion(
    session_factory: async_sessionmaker[AsyncSession],
    exportacion_id: uuid.UUID,
    *,
    config: ConfiguracionExportacion,
    ahora: datetime | None = None,
) -> Exportacion | None:
    """Claim, generate outside the transaction and persist only with the claim."""
    momento = ahora or datetime.now(timezone.utc)
    token = uuid.uuid4()
    async with UnitOfWork(session_factory) as uow:
        reclamada = await uow.exportaciones.reclamar(
            exportacion_id,
            token=token,
            ahora=momento,
            claim_timeout_seconds=config.claim_timeout_seconds,
        )
        if reclamada is None:
            return await uow.exportaciones.get(exportacion_id)
        snapshot = (
            reclamada.consultorio_id,
            reclamada.alcance,
            reclamada.paciente_id,
        )

    consultorio_id, alcance, paciente_id = snapshot
    try:
        contenido = await generar_artefacto(
            session_factory,
            exportacion_id=exportacion_id,
            consultorio_id=consultorio_id,
            alcance=alcance,
            paciente_id=paciente_id,
            config=config,
            generado_en=momento,
        )
    except LimiteExportacion as error:
        async with UnitOfWork(session_factory) as uow:
            actual = await uow.exportaciones.marcar_fallida(
                exportacion_id, token=token, error=str(error)
            )
            if actual is not None:
                await auditar(
                    uow,
                    accion="exportacion.fallida",
                    entidad="exportacion",
                    entidad_id=exportacion_id,
                    usuario_id=None,
                )
            return actual
    except Exception as error:  # noqa: BLE001 - worker boundary
        async with UnitOfWork(session_factory) as uow:
            actual = await uow.exportaciones.get(exportacion_id)
            if (
                actual is None
                or actual.claim_token != token
                or actual.estado != "generando"
            ):
                return actual
            nuevo_intentos = actual.intentos + 1
            if nuevo_intentos >= config.max_intentos:
                actual = await uow.exportaciones.marcar_fallida(
                    exportacion_id,
                    token=token,
                    error=str(error),
                    intentos=nuevo_intentos,
                )
                if actual is not None:
                    await auditar(
                        uow,
                        accion="exportacion.fallida",
                        entidad="exportacion",
                        entidad_id=exportacion_id,
                        usuario_id=None,
                    )
            else:
                actual = await uow.exportaciones.registrar_reintento(
                    exportacion_id,
                    token=token,
                    proximo_intento=proximo_intento_con_backoff(
                        momento, nuevo_intentos
                    ),
                    error=str(error),
                )
            return actual

    async with UnitOfWork(session_factory) as uow:
        actual = await uow.exportaciones.marcar_lista(
            exportacion_id,
            token=token,
            contenido=contenido,
            ahora=momento,
        )
        if actual is not None:
            await auditar(
                uow,
                accion="exportacion.generar",
                entidad="exportacion",
                entidad_id=exportacion_id,
                usuario_id=None,
            )
        return actual


async def solicitar_exportacion(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    alcance: str,
    paciente_id: uuid.UUID | None,
    redis_client: object | None = None,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> tuple[Exportacion, bool]:
    """Create (or reuse) the durable job for this scope and requester (D7)."""
    roles = _roles(usuario)
    solicitado_por = usuario.id
    if alcance == "consultorio" and "administrador" not in roles:
        raise _prohibido()
    if alcance not in {"paciente", "consultorio"}:
        raise _prohibido()

    if alcance == "paciente":
        if paciente_id is None:
            raise _no_encontrado("Paciente no encontrado")
        paciente = await uow.pacientes.get(paciente_id)
        if (
            paciente is None
            or paciente.consultorio_id != consultorio_id
            or not paciente.is_active
            or paciente.deleted_at is not None
        ):
            raise _no_encontrado("Paciente no encontrado")
        if "administrador" not in roles:
            if "odontologo" not in roles:
                raise _prohibido()
            profesional = await uow.profesionales.get_by_usuario(usuario.id)
            if profesional is None or not profesional.is_active:
                raise _prohibido()
            tiene_turno = await uow.turnos.existe_para_paciente(
                paciente.id,
                estados=ESTADOS_TURNO,
                profesional_id=profesional.id,
            )
            presupuestos = await uow.presupuestos.list_filtrado(
                consultorio_id,
                paciente_id=paciente.id,
                profesional_id=profesional.id,
            )
            if not tiene_turno and not presupuestos:
                raise _prohibido()

    existente = await uow.exportaciones.get_en_curso(
        consultorio_id=consultorio_id,
        solicitado_por=solicitado_por,
        alcance=alcance,
        paciente_id=paciente_id,
    )
    if existente is not None:
        return existente, False

    exportacion = Exportacion(
        consultorio_id=consultorio_id,
        solicitado_por=solicitado_por,
        alcance=alcance,
        paciente_id=paciente_id,
        estado="pendiente",
    )
    try:
        await uow.exportaciones.add(exportacion)
    except Exception as error:  # IntegrityError from the partial unique index
        sqlstate = getattr(getattr(error, "orig", error), "sqlstate", None)
        if sqlstate == "23505":
            await uow.session.rollback()
            existente = await uow.exportaciones.get_en_curso(
                consultorio_id=consultorio_id,
                solicitado_por=solicitado_por,
                alcance=alcance,
                paciente_id=paciente_id,
            )
            if existente is not None:
                return existente, False
        raise

    await auditar(
        uow,
        accion="exportacion.solicitar",
        entidad="exportacion",
        entidad_id=exportacion.id,
        usuario_id=solicitado_por,
        ip=ip,
        dispositivo=dispositivo,
    )
    if redis_client is not None:
        await try_enqueue(
            redis_client, REPORTES_GENERAR, str(exportacion.id)
        )
    return exportacion, True


async def descargar_exportacion(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    exportacion_id: uuid.UUID,
    usuario: Usuario,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> Exportacion:
    """Resolve a ready artifact, audit the download and return it (D10)."""
    exportacion = await obtener_exportacion(
        uow,
        consultorio_id=consultorio_id,
        exportacion_id=exportacion_id,
        usuario=usuario,
    )
    if exportacion.estado != "lista":
        raise _conflicto(
            exportacion.ultimo_error
            if exportacion.estado == "fallida"
            and exportacion.ultimo_error
            else "La exportación todavía no está lista"
        )
    await auditar(
        uow,
        accion="exportacion.descargar",
        entidad="exportacion",
        entidad_id=exportacion.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    return exportacion


async def obtener_exportacion(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    exportacion_id: uuid.UUID,
    usuario: Usuario,
) -> Exportacion:
    """Tenant + ownership isolation for state and download (D9)."""
    exportacion = await uow.exportaciones.get(exportacion_id)
    roles = _roles(usuario)
    if (
        exportacion is None
        or exportacion.consultorio_id != consultorio_id
        or (
            "administrador" not in roles
            and exportacion.solicitado_por != usuario.id
        )
    ):
        raise _no_encontrado("Exportación no encontrada")
    return exportacion


async def run_once_reportes(
    settings: Settings,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    redis_client: object | None = None,
    timeout: int = 1,
    ahora: datetime | None = None,
    config: ConfiguracionExportacion | None = None,
) -> int:
    """Pop one job (best effort) and sweep due pending rows without Redis."""
    engine = None
    if session_factory is None:
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = redis_client
    owns_redis = redis is None
    if redis is None:
        redis = get_redis_client(settings.redis_url)
    momento = ahora or datetime.now(timezone.utc)
    cfg = config or configuracion_exportacion(settings)
    procesados = 0
    job_id: uuid.UUID | None = None
    try:
        job = None
        try:
            job = await redis.brpop(REPORTES_GENERAR, timeout=timeout)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - Redis is only an accelerator
            job = None
        if job is not None:
            _, raw_id = job
            try:
                job_id = uuid.UUID(raw_id)
            except (TypeError, ValueError):
                job_id = None
            if job_id is not None:
                resultado = await procesar_exportacion(
                    session_factory,
                    job_id,
                    config=cfg,
                    ahora=momento,
                )
                if resultado is not None and resultado.estado == "lista":
                    procesados += 1

        async with UnitOfWork(session_factory) as uow:
            pendientes = await uow.exportaciones.list_pendientes_vencidos(
                momento,
                limite=100,
                claim_timeout_seconds=cfg.claim_timeout_seconds,
            )
            ids = [
                pendiente.id
                for pendiente in pendientes
                if pendiente.id != job_id
            ]
        for exportacion_id in ids:
            resultado = await procesar_exportacion(
                session_factory,
                exportacion_id,
                config=cfg,
                ahora=momento,
            )
            if resultado is not None and resultado.estado == "lista":
                procesados += 1
        return procesados
    finally:
        if owns_redis:
            await redis.aclose()  # type: ignore[union-attr]
        if engine is not None:
            await engine.dispose()
