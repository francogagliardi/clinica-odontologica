"""Payment use cases: cash, deposit, treatment, Mercado Pago and loss (C-13).

Design D2/D7/D10: the webhook is synchronous and idempotent; PostgreSQL unique
indexes resolve races, while the service validates first to return clear 4xx
codes. `Turno.sena_estado` remains the source of truth for deposits; this module
only mirrors it into `Cobro.estado` inside the same transaction.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.application.clinica import (
    auditar,
    profesional_del_usuario,
    roles_activos,
)
from app.application.comprobantes import (
    ConfiguracionFiscal,
    crear_para_cobro,
)
from app.domain.caja import (
    fecha_local,
    validar_medio,
    validar_monto,
    validar_referencias,
    validar_tipo,
)
from app.domain.turnos import ESTADOS_ACTIVOS
from app.infrastructure.mercadopago import MercadoPagoClient, PagoNormalizado
from app.infrastructure.uow import UnitOfWork
from app.models.agenda import Turno
from app.models.caja import CajaDiaria, Cobro, MovimientoCaja
from app.models.comercial import Prestacion, Presupuesto
from app.models.pacientes import Paciente
from app.models.security import Usuario

ROLES_LECTURA_COBROS = frozenset(
    {"administrador", "recepcionista", "auditor", "odontologo"}
)
ROLES_LECTURA_TOTAL_COBROS = frozenset(
    {"administrador", "recepcionista", "auditor"}
)
ESTADOS_PRESUPUESTO_COBRABLE = frozenset({"aceptado", "en_curso"})

logger = logging.getLogger("app.cobros")


@dataclass(frozen=True)
class ComandoCobro:
    """Input of a new payment, independent from the HTTP schema."""

    paciente_id: uuid.UUID
    tipo: str
    medio: str
    monto: Decimal
    turno_id: uuid.UUID | None = None
    presupuesto_id: uuid.UUID | None = None


def ahora_utc() -> datetime:
    """Single clock seam: tests freeze the cancellation boundary here."""
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


async def _resolver_paciente(
    uow: UnitOfWork, consultorio_id: uuid.UUID, paciente_id: uuid.UUID
) -> Paciente:
    paciente = await uow.pacientes.get(paciente_id)
    if (
        paciente is None
        or paciente.consultorio_id != consultorio_id
        or not paciente.is_active
        or paciente.deleted_at is not None
    ):
        raise _not_found("Paciente no encontrado")
    return paciente


async def _resolver_turno(
    uow: UnitOfWork, consultorio_id: uuid.UUID, turno_id: uuid.UUID
) -> Turno:
    turno = await uow.turnos.get(turno_id)
    if (
        turno is None
        or turno.consultorio_id != consultorio_id
        or not turno.is_active
        or turno.deleted_at is not None
    ):
        raise _not_found("Turno no encontrado")
    return turno


async def _resolver_presupuesto(
    uow: UnitOfWork, consultorio_id: uuid.UUID, presupuesto_id: uuid.UUID
) -> Presupuesto:
    presupuesto = await uow.presupuestos.get(presupuesto_id)
    if (
        presupuesto is None
        or presupuesto.consultorio_id != consultorio_id
        or presupuesto.deleted_at is not None
    ):
        raise _not_found("Presupuesto no encontrado")
    return presupuesto


async def _validar_sena(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    paciente: Paciente,
    turno_id: uuid.UUID,
    monto: Decimal,
) -> Turno:
    """RN-TU-08/RN-AD-02: only the service's exact deposit is chargeable."""
    turno = await _resolver_turno(uow, consultorio_id, turno_id)
    if turno.paciente_id != paciente.id:
        raise _unprocessable("El turno no pertenece al paciente del cobro")
    if turno.estado not in ESTADOS_ACTIVOS:
        raise _unprocessable(
            "No se cobra una seña de un turno cancelado, ausente o cerrado"
        )
    if turno.prestacion_id is None:
        raise _unprocessable("El turno no tiene una prestación con seña")
    prestacion = await uow.prestaciones.get(turno.prestacion_id)
    if (
        prestacion is None
        or not prestacion.is_active
        or prestacion.deleted_at is not None
    ):
        raise _unprocessable("La prestación del turno no está disponible")
    if not prestacion.requiere_sena or prestacion.monto_sena is None:
        raise _unprocessable("La prestación no exige seña")
    if monto != prestacion.monto_sena:
        raise _unprocessable(
            "El monto de la seña no coincide con el monto vigente"
        )
    if (
        await uow.cobros.get_sena_viva_por_turno(turno.id) is not None
    ):
        raise _conflict("El turno ya tiene una seña viva")
    return turno


async def _validar_tratamiento(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    paciente: Paciente,
    presupuesto_id: uuid.UUID,
    monto: Decimal,
) -> Decimal:
    """Partial payments up to the budget's copayment; returns the balance."""
    presupuesto = await _resolver_presupuesto(
        uow, consultorio_id, presupuesto_id
    )
    if presupuesto.paciente_id != paciente.id:
        raise _unprocessable(
            "El presupuesto no pertenece al paciente del cobro"
        )
    if presupuesto.estado not in ESTADOS_PRESUPUESTO_COBRABLE:
        raise _conflict(
            "Solo se cobra contra un presupuesto aceptado o en curso"
        )
    cobrado = await uow.cobros.sumar_tratamientos_aprobados(
        presupuesto.id
    )
    if cobrado + monto > presupuesto.copago:
        raise _conflict("El cobro excede el copago pendiente del presupuesto")
    return presupuesto.copago - (cobrado + monto)


async def _caja_abierta(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    fecha: date,
    *,
    for_update: bool = True,
) -> CajaDiaria:
    """Cash and manual movements require an already open register (D10)."""
    caja = await uow.cajas.get_por_consultorio_fecha(
        consultorio_id, fecha, for_update=for_update
    )
    if caja is None or caja.estado != "abierta":
        raise _conflict(
            "La caja de la fecha no existe o está cerrada"
        )
    return caja


async def _caja_mp(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    fecha: date,
    *,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> CajaDiaria:
    """Mercado Pago income opens the day with zero cash if needed (D10).

    The unique `(consultorio_id, fecha)` is the race resolver: if another
    request wins, the IntegrityError is translated by re-reading the row.
    """
    caja = await uow.cajas.get_por_consultorio_fecha(
        consultorio_id, fecha, for_update=True
    )
    if caja is not None:
        if caja.estado != "abierta":
            raise _conflict("La caja de la fecha está cerrada")
        return caja

    creada = False
    try:
        async with uow.session.begin_nested():
            caja = await uow.cajas.add(
                CajaDiaria(
                    consultorio_id=consultorio_id,
                    fecha=fecha,
                    estado="abierta",
                    monto_apertura=Decimal("0.00"),
                )
            )
            creada = True
    except IntegrityError:
        caja = await uow.cajas.get_por_consultorio_fecha(
            consultorio_id, fecha, for_update=True
        )
        if caja is None:
            raise _conflict("No se pudo resolver la caja del día")
        if caja.estado != "abierta":
            raise _conflict("La caja de la fecha está cerrada")
    if creada:
        await auditar(
            uow,
            accion="caja.abrir",
            entidad="caja",
            entidad_id=caja.id,
            usuario_id=None,
            ip=ip,
            dispositivo=dispositivo,
        )
    return caja


def _to_cobro(
    *,
    cobro_id: uuid.UUID,
    consultorio_id: uuid.UUID,
    paciente_id: uuid.UUID,
    comando: ComandoCobro,
    estado: str,
    fecha_operacion: date,
    fecha_conciliacion: datetime | None,
    usuario: Usuario,
) -> Cobro:
    return Cobro(
        id=cobro_id,
        consultorio_id=consultorio_id,
        paciente_id=paciente_id,
        turno_id=comando.turno_id,
        presupuesto_id=comando.presupuesto_id,
        creado_por=usuario.id,
        tipo=comando.tipo,
        medio=comando.medio,
        estado=estado,
        monto=comando.monto,
        fecha_operacion=fecha_operacion,
        fecha_conciliacion=fecha_conciliacion,
    )


async def _movimiento_ingreso(
    uow: UnitOfWork,
    *,
    caja_id: uuid.UUID,
    cobro: Cobro,
    creado_por: uuid.UUID | None,
) -> MovimientoCaja:
    return await uow.movimientos_caja.add(
        MovimientoCaja(
            caja_id=caja_id,
            tipo="ingreso",
            concepto=f"Cobro {cobro.tipo}",
            monto=cobro.monto,
            medio=cobro.medio,
            cobro_id=cobro.id,
            creado_por=creado_por,
        )
    )


async def crear_cobro(
    uow: UnitOfWork,
    mp_client: MercadoPagoClient,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    comando: ComandoCobro,
    fiscal: ConfiguracionFiscal,
    ip: str | None = None,
    dispositivo: str | None = None,
    redis_client: object | None = None,
) -> tuple[Cobro, Decimal | None]:
    """Validate per type, persist the payment and mirror it in the register."""
    paciente = await _resolver_paciente(
        uow, consultorio_id, comando.paciente_id
    )
    try:
        validar_tipo(comando.tipo)
        validar_medio(comando.medio)
        validar_monto(comando.monto)
        validar_referencias(
            comando.tipo,
            turno_id=comando.turno_id,
            presupuesto_id=comando.presupuesto_id,
        )
    except ValueError as error:
        raise _unprocessable(str(error)) from error

    saldo: Decimal | None = None
    if comando.tipo == "sena":
        assert comando.turno_id is not None
        await _validar_sena(
            uow,
            consultorio_id=consultorio_id,
            paciente=paciente,
            turno_id=comando.turno_id,
            monto=comando.monto,
        )
    elif comando.tipo == "tratamiento":
        assert comando.presupuesto_id is not None
        saldo = await _validar_tratamiento(
            uow,
            consultorio_id=consultorio_id,
            paciente=paciente,
            presupuesto_id=comando.presupuesto_id,
            monto=comando.monto,
        )

    ahora = ahora_utc()
    fecha_operacion = fecha_local(ahora)
    cobro_id = uuid.uuid4()
    preferencia = None

    if comando.medio == "efectivo":
        caja = await _caja_abierta(
            uow, consultorio_id, fecha_operacion
        )
        estado = "aprobado"
        fecha_conciliacion = ahora
    else:
        caja = None
        estado = "pendiente"
        fecha_conciliacion = None
        try:
            preferencia = await mp_client.crear_preferencia(
                cobro_id=cobro_id,
                monto=comando.monto,
                descripcion=f"Cobro {comando.tipo}",
            )
        except Exception as error:  # provider outage → 503, no orphan row
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Mercado Pago no está disponible",
            ) from error

    cobro = _to_cobro(
        cobro_id=cobro_id,
        consultorio_id=consultorio_id,
        paciente_id=paciente.id,
        comando=comando,
        estado=estado,
        fecha_operacion=fecha_operacion,
        fecha_conciliacion=fecha_conciliacion,
        usuario=usuario,
    )
    if preferencia is not None:
        cobro.proveedor_preferencia_id = preferencia.preferencia_id
        cobro.link_pago = preferencia.link_pago

    try:
        await uow.cobros.add(cobro)
    except IntegrityError as error:
        if _sqlstate(error) == "23505":
            raise _conflict(
                "El turno ya tiene una seña viva o el pago ya existe"
            ) from error
        raise

    if comando.medio == "efectivo":
        assert caja is not None
        try:
            await _movimiento_ingreso(
                uow, caja_id=caja.id, cobro=cobro, creado_por=usuario.id
            )
        except IntegrityError as error:
            if _sqlstate(error) == "23505":
                raise _conflict(
                    "El cobro ya tiene un movimiento de caja"
                ) from error
            raise
        if comando.tipo == "sena":
            assert comando.turno_id is not None
            turno = await uow.turnos.get(comando.turno_id)
            if turno is not None:
                turno.sena_estado = "pagada"

    await auditar(
        uow,
        accion="cobro.crear",
        entidad="cobro",
        entidad_id=cobro.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    if cobro.estado == "aprobado":
        await crear_para_cobro(
            uow,
            cobro=cobro,
            config=fiscal,
            usuario_id=usuario.id,
            ip=ip,
            dispositivo=dispositivo,
            redis_client=redis_client,
        )
    return cobro, saldo


async def listar_cobros(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    paciente_id: uuid.UUID | None = None,
    turno_id: uuid.UUID | None = None,
    presupuesto_id: uuid.UUID | None = None,
    estado: str | None = None,
    medio: str | None = None,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    profesional_id: uuid.UUID | None = None,
) -> list[Cobro]:
    roles = roles_activos(usuario)
    if not roles & ROLES_LECTURA_COBROS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes",
        )
    if "administrador" not in roles and "odontologo" in roles:
        propio = await profesional_del_usuario(uow, usuario)
        if propio is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El usuario no tiene un profesional vinculado",
            )
        profesional_id = propio.id
    return await uow.cobros.list_filtrado(
        consultorio_id,
        paciente_id=paciente_id,
        turno_id=turno_id,
        presupuesto_id=presupuesto_id,
        estado=estado,
        medio=medio,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        profesional_id=profesional_id,
    )


async def _exigir_lectura_cobro(
    uow: UnitOfWork, usuario: Usuario, cobro: Cobro
) -> None:
    roles = roles_activos(usuario)
    if roles & ROLES_LECTURA_TOTAL_COBROS:
        return
    if "odontologo" in roles:
        propio = await profesional_del_usuario(uow, usuario)
        if propio is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés acceso a este cobro",
            )
        if cobro.turno_id is not None:
            turno = await uow.turnos.get(cobro.turno_id)
            if turno is not None and turno.profesional_id == propio.id:
                return
        if cobro.presupuesto_id is not None:
            presupuesto = await uow.presupuestos.get(cobro.presupuesto_id)
            if (
                presupuesto is not None
                and presupuesto.profesional_id == propio.id
            ):
                return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tenés acceso a este cobro",
    )


async def obtener_cobro(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    cobro_id: uuid.UUID,
) -> tuple[Cobro, Decimal | None]:
    cobro = await uow.cobros.get(cobro_id)
    if (
        cobro is None
        or cobro.consultorio_id != consultorio_id
        or cobro.deleted_at is not None
    ):
        raise _not_found("Cobro no encontrado")
    await _exigir_lectura_cobro(uow, usuario, cobro)

    saldo: Decimal | None = None
    if cobro.tipo == "tratamiento" and cobro.presupuesto_id is not None:
        presupuesto = await uow.presupuestos.get(cobro.presupuesto_id)
        if presupuesto is not None:
            cobrado = await uow.cobros.sumar_tratamientos_aprobados(
                presupuesto.id
            )
            saldo = presupuesto.copago - cobrado
    return cobro, saldo


async def reembolsar_cobro(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    cobro_id: uuid.UUID,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> Cobro:
    """Only state + audit in v1: no provider call and no automatic cash exit.

    Repeating the operation is idempotent (200, no second audit), as required by
    `caja/cobros` and design D5.
    """
    cobro = await uow.cobros.get(cobro_id)
    if (
        cobro is None
        or cobro.consultorio_id != consultorio_id
        or cobro.deleted_at is not None
    ):
        raise _not_found("Cobro no encontrado")
    if cobro.estado == "reembolsado":
        return cobro
    if cobro.estado != "aprobado":
        raise _conflict("Solo se reembolsa un cobro aprobado")

    cobro.estado = "reembolsado"
    await uow.session.flush()
    await auditar(
        uow,
        accion="cobro.reembolsar",
        entidad="cobro",
        entidad_id=cobro.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    return cobro


async def conciliar_pago(
    uow: UnitOfWork,
    pago: PagoNormalizado,
    *,
    fiscal: ConfiguracionFiscal,
    ip: str | None = None,
    dispositivo: str | None = None,
    redis_client: object | None = None,
) -> Cobro:
    """Resolve the external reference and apply the payment idempotently (D2)."""
    cobro = await uow.cobros.get(pago.cobro_id)
    if (
        cobro is None
        or cobro.deleted_at is not None
        or not cobro.is_active
    ):
        raise _not_found("Referencia externa desconocida")

    existente = await uow.cobros.get_by_proveedor_pago_id(
        pago.proveedor_pago_id
    )
    if existente is not None:
        if existente.id == cobro.id:
            return cobro
        logger.warning(
            "Pago %s ya utilizado en el cobro %s; llega para %s",
            pago.proveedor_pago_id,
            existente.id,
            cobro.id,
        )
        raise _conflict(
            "El pago ya fue utilizado para otro cobro"
        )
    # A refunded/lost payment is terminal: a late approval is acknowledged
    # without changing anything (design D5/D7).
    if cobro.estado in {"reembolsado", "perdido"}:
        return cobro
    if cobro.proveedor_pago_id is not None:
        logger.warning(
            "Segundo pago %s para la seña ya pagada del cobro %s",
            pago.proveedor_pago_id,
            cobro.id,
        )
        raise _conflict(
            "La seña ya fue pagada con otro pago"
        )

    if pago.estado == "pendiente":
        return cobro
    if pago.estado == "rechazado":
        if cobro.estado == "pendiente":
            cobro.estado = "rechazado"
            cobro.proveedor_pago_id = pago.proveedor_pago_id
            cobro.fecha_conciliacion = ahora_utc()
            await uow.session.flush()
            await auditar(
                uow,
                accion="cobro.conciliar",
                entidad="cobro",
                entidad_id=cobro.id,
                usuario_id=None,
                ip=ip,
                dispositivo=dispositivo,
            )
        return cobro

    if pago.estado != "aprobado":
        return cobro

    if cobro.medio != "mercadopago":
        raise _conflict(
            "El pago de Mercado Pago no corresponde a un cobro en efectivo"
        )
    if cobro.estado == "aprobado":
        raise _conflict("La seña ya fue aprobada con otro pago")
    if cobro.estado != "pendiente":
        return cobro
    if pago.monto != cobro.monto or pago.moneda != "ARS":
        logger.warning(
            "Pago %s no coincide con el cobro %s: %s %s vs %s ARS",
            pago.proveedor_pago_id,
            cobro.id,
            pago.monto,
            pago.moneda,
            cobro.monto,
        )
        raise _conflict(
            "El monto o la moneda del pago no coinciden con el cobro"
        )

    fecha_conciliacion = ahora_utc()
    caja = await _caja_mp(
        uow,
        cobro.consultorio_id,
        fecha_local(fecha_conciliacion),
        ip=ip,
        dispositivo=dispositivo,
    )

    try:
        async with uow.session.begin_nested():
            cobro.estado = "aprobado"
            cobro.proveedor_pago_id = pago.proveedor_pago_id
            cobro.fecha_conciliacion = fecha_conciliacion
            await _movimiento_ingreso(
                uow, caja_id=caja.id, cobro=cobro, creado_por=None
            )
            if cobro.tipo == "sena" and cobro.turno_id is not None:
                turno = await uow.turnos.get(cobro.turno_id)
                if turno is not None and turno.sena_estado != "perdida":
                    turno.sena_estado = "pagada"
            await uow.session.flush()
            await auditar(
                uow,
                accion="cobro.conciliar",
                entidad="cobro",
                entidad_id=cobro.id,
                usuario_id=None,
                ip=ip,
                dispositivo=dispositivo,
            )
            await crear_para_cobro(
                uow,
                cobro=cobro,
                config=fiscal,
                usuario_id=None,
                ip=ip,
                dispositivo=dispositivo,
                redis_client=redis_client,
            )
    except IntegrityError as error:
        if _sqlstate(error) != "23505":
            raise
        await uow.session.refresh(cobro)
        existente = await uow.cobros.get_by_proveedor_pago_id(
            pago.proveedor_pago_id
        )
        if existente is not None and existente.id == cobro.id:
            # The same payment arrived twice concurrently: 200, no duplicate.
            return existente
        raise _conflict(
            "El pago ya fue procesado para este cobro"
        ) from error

    return cobro


def es_cancelacion_tardia(
    inicio: datetime,
    plazo_cancelacion_horas: int,
    *,
    ahora: datetime | None = None,
) -> bool:
    """Exactly at the limit is NOT late (agenda/turnos scenario)."""
    instante = ahora or ahora_utc()
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    limite = inicio - timedelta(hours=plazo_cancelacion_horas)
    return instante > limite


async def sincronizar_sena_perdida(
    uow: UnitOfWork,
    turno: Turno,
    *,
    usuario_id: uuid.UUID | None = None,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> Cobro | None:
    """Mirror `Turno.sena_estado='perdida'` into the live deposit (D4).

    The money already collected is never reversed; only the state changes and
    the audit row is appended. Repeating it is a no-op.
    """
    if turno.sena_estado != "perdida":
        return None
    cobro = await uow.cobros.get_sena_viva_por_turno(turno.id)
    if cobro is None or cobro.estado == "perdido":
        return cobro
    if cobro.estado not in {"pendiente", "aprobado"}:
        return cobro

    cobro.estado = "perdido"
    if cobro.fecha_conciliacion is None:
        cobro.fecha_conciliacion = ahora_utc()
    await uow.session.flush()
    await auditar(
        uow,
        accion="cobro.perder",
        entidad="cobro",
        entidad_id=cobro.id,
        usuario_id=usuario_id,
        ip=ip,
        dispositivo=dispositivo,
    )
    return cobro
