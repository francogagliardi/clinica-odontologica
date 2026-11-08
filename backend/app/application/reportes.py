"""Read-only report use cases (C-15, design D8/D9/D10/D13).

Totals come from `ConsultaReportesRepository` (SQL over the whole range); the
detail is bounded and ordered, and truncating it never changes a total. Nothing
here writes or audits: reports are repeated reads, and D10 keeps the audit table
for the sensitive write/export events.

The professional scope is resolved here, not in the client:

- admin, reception and auditor may filter any professional (or none);
- the dentist is always narrowed to their own professional; requesting another
  `profesional_id` is 403;
- reception has no settlement report (the router guard answers 403).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException, status

from app.domain.reportes import (
    fecha_local,
    ocupacion_porcentaje,
    rango_local_a_utc,
    sin_agenda,
    sin_cierres,
    tasa_ausentismo,
    tasa_no_asistencia,
)
from app.domain.turnos import TZ_ARGENTINA
from app.infrastructure.uow import UnitOfWork
from app.models.security import Usuario
from app.schemas.reportes import (
    AgendaProfesional,
    AgendaSillon,
    AusentismoProfesional,
    CajaReporte,
    DetalleCobro,
    DetalleLiquidacion,
    DetalleTurno,
    LiquidacionEstado,
    LiquidacionObraSocialResumen,
    MovimientoResumen,
    PracticaPrestacion,
    ReporteAgendaResponse,
    ReporteAusentismoResponse,
    ReporteCajaResponse,
    ReporteLiquidacionesResponse,
)

ESTADOS_TURNO: tuple[str, ...] = (
    "reservado",
    "confirmado",
    "en_sala",
    "atendido",
    "cancelado",
    "ausente",
)
TURNOS_CERRADOS: tuple[str, ...] = ("atendido", "cancelado", "ausente")
ESTADOS_COBRO: tuple[str, ...] = (
    "pendiente",
    "aprobado",
    "rechazado",
    "reembolsado",
    "perdido",
)


def _roles(usuario: Usuario) -> set[str]:
    return {
        rol.nombre
        for rol in usuario.roles
        if rol.is_active and rol.deleted_at is None
    }


def _prohibido() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permisos insuficientes",
    )


def _no_encontrado(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=detalle
    )


async def _validar_profesional(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    profesional_id: uuid.UUID,
):
    profesional = await uow.profesionales.get(profesional_id)
    if (
        profesional is None
        or profesional.consultorio_id != consultorio_id
        or not profesional.is_active
        or profesional.deleted_at is not None
    ):
        raise _no_encontrado("Profesional no encontrado")
    return profesional


async def _profesional_para_consulta(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    solicitado: uuid.UUID | None,
) -> uuid.UUID | None:
    """Effective professional filter for agenda/absence/cash (D9)."""
    roles = _roles(usuario)
    if roles & {"administrador", "auditor", "recepcionista"}:
        if solicitado is not None:
            await _validar_profesional(uow, consultorio_id, solicitado)
        return solicitado
    if "odontologo" in roles:
        propio = await uow.profesionales.get_by_usuario(usuario.id)
        if propio is None or not propio.is_active:
            raise _prohibido()
        if solicitado is not None and solicitado != propio.id:
            raise _prohibido()
        return propio.id
    raise _prohibido()


async def _profesional_implicito(
    uow: UnitOfWork, usuario: Usuario
) -> uuid.UUID | None:
    """Dentist's own professional for the cash report (no explicit filter)."""
    roles = _roles(usuario)
    if roles & {"administrador", "auditor", "recepcionista"}:
        return None
    if "odontologo" in roles:
        propio = await uow.profesionales.get_by_usuario(usuario.id)
        if propio is None or not propio.is_active:
            raise _prohibido()
        return propio.id
    raise _prohibido()


def _metadata(
    desde: date,
    hasta: date,
    filtros: dict[str, str | int | None],
) -> dict[str, object]:
    return {
        "generado_en": datetime.now(TZ_ARGENTINA),
        "desde": desde,
        "hasta": hasta,
        "zona_horaria": "UTC-3",
        "filtros": filtros,
    }


def _detalle_turno(turno) -> DetalleTurno:
    return DetalleTurno(
        turno_id=turno.id,
        paciente_id=turno.paciente_id,
        profesional_id=turno.profesional_id,
        sillon_id=turno.sillon_id,
        inicio=turno.inicio.astimezone(TZ_ARGENTINA),
        fin=turno.fin.astimezone(TZ_ARGENTINA),
        estado=turno.estado,
        es_sobreturno=turno.es_sobreturno,
        fecha_local=fecha_local(turno.inicio),
    )


async def reporte_agenda(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    desde: date,
    hasta: date,
    profesional_id: uuid.UUID | None = None,
    sillon_id: uuid.UUID | None = None,
    estado: str | None = None,
    limite: int = 500,
) -> ReporteAgendaResponse:
    scope = await _profesional_para_consulta(
        uow, consultorio_id, usuario, profesional_id
    )
    desde_utc, hasta_utc = rango_local_a_utc(desde, hasta)

    conteo = await uow.reportes.agenda_por_estado(
        consultorio_id,
        desde=desde_utc,
        hasta=hasta_utc,
        profesional_id=scope,
        sillon_id=sillon_id,
        estado=estado,
    )
    por_estado = {nombre: int(conteo.get(nombre, 0)) for nombre in ESTADOS_TURNO}

    por_profesional = await uow.reportes.agenda_por_profesional(
        consultorio_id,
        desde=desde_utc,
        hasta=hasta_utc,
        profesional_id=scope,
        sillon_id=sillon_id,
        estado=estado,
    )
    por_sillon = await uow.reportes.agenda_por_sillon(
        consultorio_id,
        desde=desde_utc,
        hasta=hasta_utc,
        profesional_id=scope,
        sillon_id=sillon_id,
        estado=estado,
    )
    disponibles = await uow.reportes.minutos_disponibles_por_profesional(
        consultorio_id,
        desde=desde,
        hasta=hasta,
        profesional_id=scope,
    )
    ocupados = await uow.reportes.minutos_ocupados_por_profesional(
        consultorio_id,
        desde=desde_utc,
        hasta=hasta_utc,
        profesional_id=scope,
        estado=estado,
    )
    sobreturnos = await uow.reportes.minutos_sobreturno_por_profesional(
        consultorio_id,
        desde=desde_utc,
        hasta=hasta_utc,
        profesional_id=scope,
        estado=estado,
    )

    turnos_por_profesional = {
        fila["profesional_id"]: int(fila["cantidad"])
        for fila in por_profesional
    }
    ids = (
        set(turnos_por_profesional)
        | set(disponibles)
        | set(ocupados)
        | set(sobreturnos)
    )
    if scope is not None:
        ids.add(scope)

    filas_profesional = [
        AgendaProfesional(
            profesional_id=profesional,
            turnos=turnos_por_profesional.get(profesional, 0),
            minutos_disponibles=disponibles.get(profesional, 0),
            minutos_ocupados=ocupados.get(profesional, 0),
            minutos_sobreturno=sobreturnos.get(profesional, 0),
            ocupacion_porcentaje=ocupacion_porcentaje(
                ocupados.get(profesional, 0),
                disponibles.get(profesional, 0),
            ),
            sin_agenda=sin_agenda(disponibles.get(profesional, 0)),
        )
        for profesional in sorted(ids)
    ]

    total_disponibles = sum(disponibles.values())
    total_ocupados = sum(ocupados.values())
    total_sobreturnos = sum(sobreturnos.values())

    detalle = await uow.reportes.turnos_detalle(
        consultorio_id,
        desde=desde_utc,
        hasta=hasta_utc,
        profesional_id=scope,
        sillon_id=sillon_id,
        estado=estado,
        limite=limite,
    )
    total_detalle = await uow.reportes.contar_turnos(
        consultorio_id,
        desde=desde_utc,
        hasta=hasta_utc,
        profesional_id=scope,
        sillon_id=sillon_id,
        estado=estado,
    )

    return ReporteAgendaResponse(
        **_metadata(
            desde,
            hasta,
            {
                "profesional_id": str(scope) if scope is not None else None,
                "sillon_id": str(sillon_id) if sillon_id is not None else None,
                "estado": estado,
                "limite": limite,
            },
        ),
        total_turnos=sum(por_estado.values()),
        por_estado=por_estado,
        cancelaciones=por_estado["cancelado"],
        por_profesional=filas_profesional,
        por_sillon=[
            AgendaSillon(
                sillon_id=fila["sillon_id"],
                turnos=int(fila["cantidad"]),
            )
            for fila in por_sillon
        ],
        minutos_disponibles=total_disponibles,
        minutos_ocupados=total_ocupados,
        minutos_sobreturno=total_sobreturnos,
        ocupacion_porcentaje=ocupacion_porcentaje(
            total_ocupados, total_disponibles
        ),
        sin_agenda=sin_agenda(total_disponibles),
        total_detalle=total_detalle,
        detalle_truncado=total_detalle > len(detalle),
        detalle=[_detalle_turno(turno) for turno in detalle],
    )


async def reporte_ausentismo(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    desde: date,
    hasta: date,
    profesional_id: uuid.UUID | None = None,
    limite: int = 500,
) -> ReporteAusentismoResponse:
    scope = await _profesional_para_consulta(
        uow, consultorio_id, usuario, profesional_id
    )
    desde_utc, hasta_utc = rango_local_a_utc(desde, hasta)

    resumen = await uow.reportes.resumen_ausentismo(
        consultorio_id,
        desde=desde_utc,
        hasta=hasta_utc,
        profesional_id=scope,
    )
    por_profesional = await uow.reportes.ausentismo_por_profesional(
        consultorio_id,
        desde=desde_utc,
        hasta=hasta_utc,
        profesional_id=scope,
    )
    filas = [
        AusentismoProfesional(
            profesional_id=fila["profesional_id"],
            atendidos=int(fila["atendidos"]),
            cancelados=int(fila["cancelados"]),
            ausentes=int(fila["ausentes"]),
            turnos_activos=int(fila["turnos_activos"]),
            tasa_ausentismo=tasa_ausentismo(
                fila["atendidos"], fila["cancelados"], fila["ausentes"]
            ),
            tasa_no_asistencia=tasa_no_asistencia(
                fila["atendidos"], fila["cancelados"], fila["ausentes"]
            ),
            sin_cierres=sin_cierres(
                fila["atendidos"], fila["cancelados"], fila["ausentes"]
            ),
        )
        for fila in por_profesional
    ]
    if scope is not None and not any(
        fila.profesional_id == scope for fila in filas
    ):
        filas.append(
            AusentismoProfesional(
                profesional_id=scope,
                atendidos=0,
                cancelados=0,
                ausentes=0,
                turnos_activos=0,
                tasa_ausentismo=Decimal("0.00"),
                tasa_no_asistencia=Decimal("0.00"),
                sin_cierres=True,
            )
        )

    detalle = await uow.reportes.turnos_detalle(
        consultorio_id,
        desde=desde_utc,
        hasta=hasta_utc,
        profesional_id=scope,
        estados=TURNOS_CERRADOS,
        limite=limite,
    )
    total_detalle = await uow.reportes.contar_turnos(
        consultorio_id,
        desde=desde_utc,
        hasta=hasta_utc,
        profesional_id=scope,
        estados=TURNOS_CERRADOS,
    )

    return ReporteAusentismoResponse(
        **_metadata(
            desde,
            hasta,
            {
                "profesional_id": str(scope) if scope is not None else None,
                "limite": limite,
            },
        ),
        atendidos=resumen["atendidos"],
        cancelados=resumen["cancelados"],
        ausentes=resumen["ausentes"],
        turnos_activos=resumen["turnos_activos"],
        tasa_ausentismo=tasa_ausentismo(
            resumen["atendidos"],
            resumen["cancelados"],
            resumen["ausentes"],
        ),
        tasa_no_asistencia=tasa_no_asistencia(
            resumen["atendidos"],
            resumen["cancelados"],
            resumen["ausentes"],
        ),
        sin_cierres=sin_cierres(
            resumen["atendidos"],
            resumen["cancelados"],
            resumen["ausentes"],
        ),
        por_profesional=filas,
        total_detalle=total_detalle,
        detalle_truncado=total_detalle > len(detalle),
        detalle=[_detalle_turno(turno) for turno in detalle],
    )


async def reporte_caja(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    desde: date,
    hasta: date,
    medio: str | None = None,
    estado: str | None = None,
    limite: int = 500,
) -> ReporteCajaResponse:
    scope = await _profesional_implicito(uow, usuario)

    totales = await uow.reportes.totales_aprobados_por_medio(
        consultorio_id,
        desde=desde,
        hasta=hasta,
        profesional_id=scope,
        medio=medio,
        estado=estado,
    )
    conteo = await uow.reportes.conteo_cobros_por_estado(
        consultorio_id,
        desde=desde,
        hasta=hasta,
        profesional_id=scope,
        medio=medio,
        estado=estado,
    )
    movimientos = await uow.reportes.movimientos_por_tipo(
        consultorio_id, desde=desde, hasta=hasta
    )
    cajas = await uow.reportes.cajas_del_rango(
        consultorio_id, desde=desde, hasta=hasta
    )
    detalle = await uow.reportes.cobros_detalle(
        consultorio_id,
        desde=desde,
        hasta=hasta,
        profesional_id=scope,
        medio=medio,
        estado=estado,
        limite=limite,
    )
    total_detalle = await uow.reportes.contar_cobros(
        consultorio_id,
        desde=desde,
        hasta=hasta,
        profesional_id=scope,
        medio=medio,
        estado=estado,
    )

    total_efectivo = totales["efectivo"]
    total_mercadopago = totales["mercadopago"]
    por_estado = {
        nombre: int(conteo.get(nombre, 0)) for nombre in ESTADOS_COBRO
    }

    return ReporteCajaResponse(
        **_metadata(
            desde,
            hasta,
            {
                "profesional_id": str(scope) if scope is not None else None,
                "medio": medio,
                "estado": estado,
                "limite": limite,
            },
        ),
        total_aprobado=total_efectivo + total_mercadopago,
        total_efectivo=total_efectivo,
        total_mercadopago=total_mercadopago,
        total_gastos=sum(
            (
                fila["total"]
                for fila in movimientos
                if fila["tipo"] == "gasto"
            ),
            Decimal("0.00"),
        ),
        total_deudas=sum(
            (
                fila["total"]
                for fila in movimientos
                if fila["tipo"] == "deuda"
            ),
            Decimal("0.00"),
        ),
        por_estado=por_estado,
        movimientos=[
            MovimientoResumen(
                tipo=fila["tipo"],
                medio=fila["medio"],
                cantidad=int(fila["cantidad"]),
                total=fila["total"],
            )
            for fila in movimientos
        ],
        cajas=[
            CajaReporte(
                caja_id=caja.id,
                fecha=caja.fecha,
                estado=caja.estado,
                monto_apertura=caja.monto_apertura,
                monto_sistema_efectivo=caja.monto_sistema_efectivo,
                monto_contado=caja.monto_contado,
                diferencia=caja.diferencia,
            )
            for caja in cajas
        ],
        total_detalle=total_detalle,
        detalle_truncado=total_detalle > len(detalle),
        detalle=[
            DetalleCobro(
                cobro_id=cobro.id,
                paciente_id=cobro.paciente_id,
                turno_id=cobro.turno_id,
                presupuesto_id=cobro.presupuesto_id,
                tipo=cobro.tipo,
                medio=cobro.medio,
                estado=cobro.estado,
                monto=cobro.monto,
                fecha_operacion=cobro.fecha_operacion,
                fecha_local=cobro.fecha_operacion,
            )
            for cobro in detalle
        ],
    )


async def _validar_obra_social(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    obra_social_id: uuid.UUID,
) -> None:
    obra_social = await uow.obras_sociales.get(obra_social_id)
    if (
        obra_social is None
        or obra_social.consultorio_id != consultorio_id
        or not obra_social.is_active
        or obra_social.deleted_at is not None
    ):
        raise _no_encontrado("Obra social no encontrada")


async def reporte_liquidaciones(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    desde: date,
    hasta: date,
    obra_social_id: uuid.UUID | None = None,
    estado: str | None = None,
    limite: int = 500,
) -> ReporteLiquidacionesResponse:
    if obra_social_id is not None:
        await _validar_obra_social(uow, consultorio_id, obra_social_id)

    agregados = await uow.reportes.liquidaciones_por_obra_estado(
        consultorio_id,
        desde=desde,
        hasta=hasta,
        obra_social_id=obra_social_id,
        estado=estado,
    )
    prestaciones = await uow.reportes.practicas_por_prestacion(
        consultorio_id,
        desde=desde,
        hasta=hasta,
        obra_social_id=obra_social_id,
        estado=estado,
    )
    cabeceras = await uow.reportes.liquidaciones_del_periodo(
        consultorio_id,
        desde=desde,
        hasta=hasta,
        obra_social_id=obra_social_id,
        estado=estado,
        limite=limite,
    )
    total_detalle = await uow.reportes.contar_liquidaciones_del_periodo(
        consultorio_id,
        desde=desde,
        hasta=hasta,
        obra_social_id=obra_social_id,
        estado=estado,
    )

    nombres: dict[uuid.UUID, str] = {}
    for fila in agregados:
        obra_id = fila["obra_social_id"]
        if obra_id not in nombres:
            obra = await uow.obras_sociales.get(obra_id)
            nombres[obra_id] = obra.nombre if obra is not None else ""

    por_estado = [
        LiquidacionEstado(
            obra_social_id=fila["obra_social_id"],
            obra_social_nombre=nombres[fila["obra_social_id"]],
            estado=fila["estado"],
            cantidad_liquidaciones=int(fila["cantidad_liquidaciones"]),
            total_cobertura=fila["total_cobertura"],
            cantidad_practicas=int(fila["cantidad_practicas"]),
        )
        for fila in agregados
    ]

    agregado_por_obra: dict[uuid.UUID, dict[str, object]] = {}
    for fila in por_estado:
        acumulado = agregado_por_obra.setdefault(
            fila.obra_social_id,
            {
                "obra_social_id": fila.obra_social_id,
                "obra_social_nombre": fila.obra_social_nombre,
                "cantidad_liquidaciones": 0,
                "total_cobertura": Decimal("0.00"),
                "cantidad_practicas": 0,
            },
        )
        acumulado["cantidad_liquidaciones"] = (
            int(acumulado["cantidad_liquidaciones"])
            + fila.cantidad_liquidaciones
        )
        acumulado["total_cobertura"] = (
            acumulado["total_cobertura"] + fila.total_cobertura
        )
        acumulado["cantidad_practicas"] = (
            int(acumulado["cantidad_practicas"])
            + fila.cantidad_practicas
        )

    return ReporteLiquidacionesResponse(
        **_metadata(
            desde,
            hasta,
            {
                "obra_social_id": (
                    str(obra_social_id)
                    if obra_social_id is not None
                    else None
                ),
                "estado": estado,
                "limite": limite,
            },
        ),
        cantidad_liquidaciones=sum(
            fila.cantidad_liquidaciones for fila in por_estado
        ),
        total_cobertura=sum(
            (fila.total_cobertura for fila in por_estado),
            Decimal("0.00"),
        ),
        cantidad_practicas=sum(
            fila.cantidad_practicas for fila in por_estado
        ),
        por_estado=por_estado,
        por_obra_social=[
            LiquidacionObraSocialResumen(**datos)
            for datos in agregado_por_obra.values()
        ],
        por_prestacion=[
            PracticaPrestacion(
                prestacion_codigo=fila["prestacion_codigo"],
                cantidad=int(fila["cantidad"]),
                cobertura=fila["cobertura"],
            )
            for fila in prestaciones
        ],
        total_detalle=total_detalle,
        detalle_truncado=total_detalle > len(cabeceras),
        detalle=[
            DetalleLiquidacion(
                liquidacion_id=cabecera.id,
                obra_social_id=cabecera.obra_social_id,
                estado=cabecera.estado,
                desde=cabecera.desde,
                hasta=cabecera.hasta,
                total_cobertura=cabecera.total_cobertura,
                cantidad_practicas=cabecera.cantidad_practicas,
            )
            for cabecera in cabeceras
        ],
    )
