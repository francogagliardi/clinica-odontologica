"""Insurance settlement use cases (C-14, design D9).

A settlement is built from covered budget lines whose budget had an approved
treatment payment inside the period. Every line snapshots the service, quantity
and covered amount and keeps the traceability to budget/item/payment required
by RN-OS-03. Periods are local, inclusive and non-overlapping; closing freezes
the totals and only a draft can be soft-deleted.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import DBAPIError

from app.application.clinica import auditar
from app.domain.liquidaciones import calcular_totales, validar_periodo
from app.infrastructure.uow import UnitOfWork
from app.models.comercial import ObraSocial, Prestacion
from app.models.liquidaciones import ItemLiquidacion, LiquidacionObraSocial
from app.models.security import Usuario


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


async def _resolver_obra_social(
    uow: UnitOfWork, consultorio_id: uuid.UUID, obra_social_id: uuid.UUID
) -> ObraSocial:
    obra = await uow.obras_sociales.get(obra_social_id)
    if (
        obra is None
        or obra.consultorio_id != consultorio_id
        or not obra.is_active
        or obra.deleted_at is not None
    ):
        raise _not_found("Obra social no encontrada")
    return obra


async def _resolver_liquidacion(
    uow: UnitOfWork, consultorio_id: uuid.UUID, liquidacion_id: uuid.UUID
) -> tuple[LiquidacionObraSocial, list[ItemLiquidacion]]:
    liquidacion, items = await uow.liquidaciones.get_con_items(
        liquidacion_id
    )
    if liquidacion is None or liquidacion.consultorio_id != consultorio_id:
        raise _not_found("Liquidación no encontrada")
    return liquidacion, items


async def crear(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    obra_social_id: uuid.UUID,
    desde: date,
    hasta: date,
    observaciones: str | None = None,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> tuple[LiquidacionObraSocial, list[ItemLiquidacion]]:
    """Create a draft with the D9 selection and frozen snapshots."""
    await _resolver_obra_social(uow, consultorio_id, obra_social_id)
    try:
        validar_periodo(desde, hasta)
    except ValueError as error:
        raise _unprocessable(str(error)) from error

    solapada = await uow.liquidaciones.get_solapada(
        consultorio_id=consultorio_id,
        obra_social_id=obra_social_id,
        desde=desde,
        hasta=hasta,
    )
    if solapada is not None:
        raise _conflict(
            "Ya existe una liquidación vigente que se solapa con el período"
        )

    seleccion = await uow.liquidaciones.list_items_liquidables(
        consultorio_id=consultorio_id,
        obra_social_id=obra_social_id,
        desde=desde,
        hasta=hasta,
    )
    if not seleccion:
        raise _unprocessable(
            "No hay prácticas liquidables para ese período"
        )

    liquidacion = LiquidacionObraSocial(
        consultorio_id=consultorio_id,
        obra_social_id=obra_social_id,
        creado_por=usuario.id,
        desde=desde,
        hasta=hasta,
        estado="borrador",
        total_cobertura=0,
        cantidad_practicas=0,
        observaciones=observaciones,
    )
    try:
        await uow.liquidaciones.add(liquidacion)
    except DBAPIError as error:
        if _sqlstate(error) == "23P01":
            raise _conflict(
                "Ya existe una liquidación vigente que se solapa "
                "con el período"
            ) from error
        raise

    prestaciones: dict[uuid.UUID, Prestacion | None] = {}
    items: list[ItemLiquidacion] = []
    for item_presupuesto, presupuesto, cobro in seleccion:
        if item_presupuesto.prestacion_id not in prestaciones:
            prestaciones[item_presupuesto.prestacion_id] = (
                await uow.prestaciones.get(item_presupuesto.prestacion_id)
            )
        prestacion = prestaciones[item_presupuesto.prestacion_id]
        if prestacion is None:  # pragma: no cover - FK guarantees it
            continue
        item = ItemLiquidacion(
            liquidacion_id=liquidacion.id,
            item_presupuesto_id=item_presupuesto.id,
            presupuesto_id=presupuesto.id,
            cobro_id=cobro.id,
            prestacion_id=prestacion.id,
            prestacion_codigo=prestacion.codigo,
            pieza=item_presupuesto.pieza,
            cantidad=item_presupuesto.cantidad,
            cobertura_item=item_presupuesto.cobertura_item,
        )
        await uow.items_liquidacion.add(item)
        items.append(item)

    totales = calcular_totales(
        [item.cobertura_item for item in items]
    )
    liquidacion.total_cobertura = totales.total_cobertura
    liquidacion.cantidad_practicas = totales.cantidad_practicas
    await uow.session.flush()
    await uow.session.refresh(liquidacion)

    await auditar(
        uow,
        accion="liquidacion.crear",
        entidad="liquidacion",
        entidad_id=liquidacion.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    return liquidacion, items


async def listar(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    obra_social_id: uuid.UUID | None = None,
    estado: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
) -> list[LiquidacionObraSocial]:
    return await uow.liquidaciones.list_filtrado(
        consultorio_id,
        obra_social_id=obra_social_id,
        estado=estado,
        desde=desde,
        hasta=hasta,
    )


async def obtener(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    liquidacion_id: uuid.UUID,
) -> tuple[LiquidacionObraSocial, list[ItemLiquidacion]]:
    return await _resolver_liquidacion(
        uow, consultorio_id, liquidacion_id
    )


async def cerrar(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    liquidacion_id: uuid.UUID,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> tuple[LiquidacionObraSocial, list[ItemLiquidacion]]:
    """Freeze the totals; repeating the close is a no-op (D9)."""
    liquidacion, items = await _resolver_liquidacion(
        uow, consultorio_id, liquidacion_id
    )
    if liquidacion.estado == "cerrada":
        return liquidacion, items
    if liquidacion.estado != "borrador":
        raise _conflict("Solo se cierra una liquidación en borrador")

    liquidacion.estado = "cerrada"
    liquidacion.cerrada_por = usuario.id
    liquidacion.cerrada_at = _ahora()
    await uow.session.flush()
    await uow.session.refresh(liquidacion)
    await auditar(
        uow,
        accion="liquidacion.cerrar",
        entidad="liquidacion",
        entidad_id=liquidacion.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    return liquidacion, items


async def actualizar_observaciones(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    liquidacion_id: uuid.UUID,
    observaciones: str | None,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> LiquidacionObraSocial:
    liquidacion, _items = await _resolver_liquidacion(
        uow, consultorio_id, liquidacion_id
    )
    if liquidacion.estado == "cerrada":
        raise _conflict(
            "Una liquidación cerrada no admite edición"
        )
    liquidacion.observaciones = observaciones
    await uow.session.flush()
    await uow.session.refresh(liquidacion)
    await auditar(
        uow,
        accion="liquidacion.editar",
        entidad="liquidacion",
        entidad_id=liquidacion.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    return liquidacion


async def eliminar(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    liquidacion_id: uuid.UUID,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> None:
    """Soft delete a draft and release its period and budget lines (D9)."""
    liquidacion, _items = await _resolver_liquidacion(
        uow, consultorio_id, liquidacion_id
    )
    if liquidacion.estado == "cerrada":
        raise _conflict(
            "Una liquidación cerrada no se puede eliminar"
        )

    await uow.items_liquidacion.soft_delete_by_liquidacion(
        liquidacion.id
    )
    await uow.liquidaciones.soft_delete(liquidacion)
    await auditar(
        uow,
        accion="liquidacion.eliminar",
        entidad="liquidacion",
        entidad_id=liquidacion.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
