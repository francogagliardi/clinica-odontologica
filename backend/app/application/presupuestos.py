"""Budget application layer: coverage seam and creation service (C-12).

The coverage provider resolves *rules*, never amounts: the arithmetic lives in
`app.domain.presupuestos`, so the same calculation is unit-tested without a
database. `None` means "not verifiable" (pending), while a known 0 % is a
`CoberturaConvenio` with `cobertura_porcentaje = 0` (design D4/D5).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol

from fastapi import HTTPException, status

from app.application.clinica import (
    ROLES_LECTURA,
    auditar,
    paciente_propio,
    profesional_del_usuario,
    roles_activos,
)
from app.domain.clinica import pieza_fdi_valida
from app.domain.presupuestos import (
    ESTADOS,
    calcular_item,
    calcular_presupuesto,
    puede_transicionar,
)
from app.infrastructure.uow import UnitOfWork
from app.models.agenda import Profesional
from app.models.comercial import ItemPresupuesto, Prestacion, Presupuesto
from app.models.pacientes import Paciente
from app.models.security import Usuario

CIEN = Decimal("100")


@dataclass(frozen=True)
class CoberturaConvenio:
    """Interpreted local rules: a percentage plus the covered service codes."""

    cobertura_porcentaje: Decimal
    prestaciones_cubiertas: frozenset[str] = frozenset()

    def cubre(self, codigo: str) -> bool:
        return codigo.strip().upper() in self.prestaciones_cubiertas


class CoberturaNoDisponible(Exception):
    """The provider could not resolve coverage; the budget stays pending."""


class CoberturaProvider(Protocol):
    async def resolver(
        self, uow: UnitOfWork, paciente: Paciente
    ) -> CoberturaConvenio | None: ...


def _porcentaje(valor: object) -> Decimal | None:
    """Decode `reglas_cobertura.cobertura_porcentaje`, or None if unusable."""
    if isinstance(valor, bool) or valor is None:
        return None
    try:
        porcentaje = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if porcentaje < 0 or porcentaje > CIEN:
        return None
    return porcentaje


class LocalCoberturaProvider:
    """v1 provider: read the patient's active convention (DD-11)."""

    async def resolver(
        self, uow: UnitOfWork, paciente: Paciente
    ) -> CoberturaConvenio | None:
        if paciente.obra_social_id is None:
            # No agreement is a known 0 %, not an unverifiable coverage.
            return CoberturaConvenio(cobertura_porcentaje=Decimal("0"))

        obra = await uow.obras_sociales.get(paciente.obra_social_id)
        if (
            obra is None
            or not obra.is_active
            or obra.deleted_at is not None
            or obra.consultorio_id != paciente.consultorio_id
        ):
            return None

        reglas = obra.reglas_cobertura
        if not isinstance(reglas, dict):
            return None
        if "cobertura_porcentaje" not in reglas:
            return None
        porcentaje = _porcentaje(reglas["cobertura_porcentaje"])
        if porcentaje is None:
            return None

        cubiertas = reglas.get("prestaciones_cubiertas", [])
        if not isinstance(cubiertas, (list, tuple)):
            return None
        if not all(isinstance(codigo, str) for codigo in cubiertas):
            return None

        return CoberturaConvenio(
            cobertura_porcentaje=porcentaje,
            prestaciones_cubiertas=frozenset(
                codigo.strip().upper()
                for codigo in cubiertas
                if codigo.strip()
            ),
        )


def get_cobertura_provider() -> CoberturaProvider:
    """FastAPI dependency; tests override it to simulate an outage."""
    return LocalCoberturaProvider()


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paciente no encontrado",
        )
    return paciente


async def _resolver_profesional(
    uow: UnitOfWork, consultorio_id: uuid.UUID, profesional_id: uuid.UUID
) -> Profesional:
    profesional = await uow.profesionales.get(profesional_id)
    if (
        profesional is None
        or profesional.consultorio_id != consultorio_id
        or not profesional.is_active
        or profesional.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profesional no encontrado",
        )
    return profesional


async def _resolver_prestacion(
    uow: UnitOfWork, prestacion_id: uuid.UUID
) -> Prestacion:
    prestacion = await uow.prestaciones.get(prestacion_id)
    if (
        prestacion is None
        or not prestacion.is_active
        or prestacion.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prestación no encontrada",
        )
    return prestacion


async def _exigir_propiedad(
    uow: UnitOfWork,
    usuario: Usuario,
    paciente: Paciente,
    profesional: Profesional,
) -> None:
    """Admin CRUD; a dentist only over their own professional and patient."""
    roles = roles_activos(usuario)
    if "administrador" in roles:
        return
    if "odontologo" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes",
        )
    propio = await profesional_del_usuario(uow, usuario)
    if propio is None or propio.id != profesional.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No podés asignar otro profesional",
        )
    if not await paciente_propio(uow, usuario, paciente.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés acceso a este paciente",
        )


async def _resolver_items(
    uow: UnitOfWork,
    items: Sequence[tuple[uuid.UUID, int | None, int]],
) -> list[tuple[Prestacion, int | None, int]]:
    resueltas: list[tuple[Prestacion, int | None, int]] = []
    for prestacion_id, pieza, cantidad in items:
        if cantidad <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="La cantidad debe ser mayor que cero",
            )
        if pieza is not None and not pieza_fdi_valida(pieza):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="La pieza no es una pieza FDI válida",
            )
        prestacion = await _resolver_prestacion(uow, prestacion_id)
        resueltas.append((prestacion, pieza, cantidad))
    if not resueltas:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El presupuesto debe tener al menos un ítem",
        )
    return resueltas


async def _resolver_cobertura(
    uow: UnitOfWork, provider: CoberturaProvider, paciente: Paciente
) -> CoberturaConvenio | None:
    try:
        return await provider.resolver(uow, paciente)
    except CoberturaNoDisponible:
        return None


def _estado_cobertura(cobertura: CoberturaConvenio | None) -> str:
    return "calculada" if cobertura is not None else "pendiente_verificacion"


def _calcular_lineas(
    resueltas: Sequence[tuple[Prestacion, int | None, int]],
    cobertura: CoberturaConvenio | None,
) -> list[tuple[Prestacion, int | None, int, Decimal, Decimal]]:
    lineas: list[tuple[Prestacion, int | None, int, Decimal, Decimal]] = []
    for prestacion, pieza, cantidad in resueltas:
        porcentaje = Decimal("0")
        if cobertura is not None and cobertura.cubre(prestacion.codigo):
            porcentaje = cobertura.cobertura_porcentaje
        cobertura_item, copago_item = calcular_item(
            prestacion.precio_base, cantidad, porcentaje
        )
        lineas.append(
            (prestacion, pieza, cantidad, cobertura_item, copago_item)
        )
    return lineas


async def _cargar_presupuesto(
    uow: UnitOfWork, consultorio_id: uuid.UUID, presupuesto_id: uuid.UUID
) -> tuple[Presupuesto, list[ItemPresupuesto]]:
    presupuesto, items = await uow.presupuestos.get_con_items(
        presupuesto_id
    )
    if presupuesto is None or presupuesto.consultorio_id != consultorio_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Presupuesto no encontrado",
        )
    return presupuesto, items


def _exigir_borrador(presupuesto: Presupuesto) -> None:
    if presupuesto.estado != "borrador":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La operación solo está permitida en un borrador",
        )


async def _exigir_lectura_existente(
    uow: UnitOfWork, usuario: Usuario, presupuesto: Presupuesto
) -> None:
    roles = roles_activos(usuario)
    if "administrador" in roles:
        return
    if "odontologo" in roles:
        propio = await profesional_del_usuario(uow, usuario)
        if propio is None or presupuesto.profesional_id != propio.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés acceso a este presupuesto",
            )
        return
    if roles & ROLES_LECTURA:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permisos insuficientes",
    )


async def _exigir_escritura_existente(
    uow: UnitOfWork, usuario: Usuario, presupuesto: Presupuesto
) -> None:
    roles = roles_activos(usuario)
    if "administrador" in roles:
        return
    if "odontologo" in roles:
        propio = await profesional_del_usuario(uow, usuario)
        if propio is None or presupuesto.profesional_id != propio.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tenés acceso a este presupuesto",
            )
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Permisos insuficientes",
    )


async def listar_presupuestos(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    paciente_id: uuid.UUID | None = None,
    profesional_id: uuid.UUID | None = None,
    estado: str | None = None,
) -> list[Presupuesto]:
    """Consultorio scope; a dentist is always narrowed to their own rows."""
    roles = roles_activos(usuario)
    if not roles & ROLES_LECTURA:
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
    return await uow.presupuestos.list_filtrado(
        consultorio_id,
        paciente_id=paciente_id,
        profesional_id=profesional_id,
        estado=estado,
    )


async def obtener_presupuesto(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    presupuesto_id: uuid.UUID,
) -> tuple[Presupuesto, list[ItemPresupuesto]]:
    presupuesto, items = await _cargar_presupuesto(
        uow, consultorio_id, presupuesto_id
    )
    await _exigir_lectura_existente(uow, usuario, presupuesto)
    return presupuesto, items


async def _exigir_profesional_propio_en_cuerpo(
    uow: UnitOfWork, usuario: Usuario, profesional: Profesional
) -> None:
    """A dentist cannot assign a budget to another professional (D9)."""
    if "administrador" in roles_activos(usuario):
        return
    propio = await profesional_del_usuario(uow, usuario)
    if propio is None or propio.id != profesional.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No podés asignar otro profesional",
        )


async def crear_presupuesto(
    uow: UnitOfWork,
    provider: CoberturaProvider,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    paciente_id: uuid.UUID,
    profesional_id: uuid.UUID,
    items: Sequence[tuple[uuid.UUID, int | None, int]],
    ip: str | None = None,
    dispositivo: str | None = None,
) -> tuple[Presupuesto, list[ItemPresupuesto]]:
    """Create a draft with server-calculated prices, coverage and totals.

    The provider only resolves rules; a `None`/`CoberturaNoDisponible` result
    becomes `pendiente_verificacion` with 0 coverage and never a 500 (D4/D5).
    """
    paciente = await _resolver_paciente(uow, consultorio_id, paciente_id)
    profesional = await _resolver_profesional(
        uow, consultorio_id, profesional_id
    )
    await _exigir_propiedad(uow, usuario, paciente, profesional)
    resueltas = await _resolver_items(uow, items)
    cobertura = await _resolver_cobertura(uow, provider, paciente)
    lineas = _calcular_lineas(resueltas, cobertura)

    totales = calcular_presupuesto(
        [(linea[3], linea[4]) for linea in lineas]
    )
    presupuesto = Presupuesto(
        consultorio_id=consultorio_id,
        paciente_id=paciente.id,
        profesional_id=profesional.id,
        creado_por=usuario.id,
        estado="borrador",
        cobertura_estado=(
            "calculada" if cobertura is not None else "pendiente_verificacion"
        ),
        subtotal=totales.subtotal,
        cobertura_calculada=totales.cobertura_calculada,
        copago=totales.copago,
    )
    await uow.presupuestos.add(presupuesto)

    persistidos: list[ItemPresupuesto] = []
    for prestacion, pieza, cantidad, cobertura_item, copago_item in lineas:
        item = ItemPresupuesto(
            presupuesto_id=presupuesto.id,
            prestacion_id=prestacion.id,
            pieza=pieza,
            cantidad=cantidad,
            precio_unitario=prestacion.precio_base,
            cobertura_item=cobertura_item,
            copago_item=copago_item,
        )
        await uow.items_presupuesto.add(item)
        persistidos.append(item)

    await auditar(
        uow,
        accion="presupuesto.crear",
        entidad="presupuesto",
        entidad_id=presupuesto.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    return presupuesto, persistidos


async def actualizar_presupuesto(
    uow: UnitOfWork,
    provider: CoberturaProvider,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    presupuesto_id: uuid.UUID,
    paciente_id: uuid.UUID,
    profesional_id: uuid.UUID,
    items: Sequence[tuple[uuid.UUID, int | None, int]],
    ip: str | None = None,
    dispositivo: str | None = None,
) -> tuple[Presupuesto, list[ItemPresupuesto]]:
    """Full replacement of a draft: re-quote prices, coverage and totals.

    The old lines are soft-deleted, never removed; the header keeps its state
    (`borrador`) and ownership is checked before touching anything.
    """
    presupuesto, _items = await _cargar_presupuesto(
        uow, consultorio_id, presupuesto_id
    )
    await _exigir_escritura_existente(uow, usuario, presupuesto)
    _exigir_borrador(presupuesto)

    paciente = await _resolver_paciente(uow, consultorio_id, paciente_id)
    profesional = await _resolver_profesional(
        uow, consultorio_id, profesional_id
    )
    await _exigir_profesional_propio_en_cuerpo(uow, usuario, profesional)
    resueltas = await _resolver_items(uow, items)
    cobertura = await _resolver_cobertura(uow, provider, paciente)
    lineas = _calcular_lineas(resueltas, cobertura)
    totales = calcular_presupuesto(
        [(linea[3], linea[4]) for linea in lineas]
    )

    await uow.items_presupuesto.desactivar_de_presupuesto(presupuesto.id)
    presupuesto.paciente_id = paciente.id
    presupuesto.profesional_id = profesional.id
    presupuesto.cobertura_estado = _estado_cobertura(cobertura)
    presupuesto.subtotal = totales.subtotal
    presupuesto.cobertura_calculada = totales.cobertura_calculada
    presupuesto.copago = totales.copago
    await uow.session.flush()
    await uow.session.refresh(presupuesto)

    persistidos: list[ItemPresupuesto] = []
    for prestacion, pieza, cantidad, cobertura_item, copago_item in lineas:
        item = ItemPresupuesto(
            presupuesto_id=presupuesto.id,
            prestacion_id=prestacion.id,
            pieza=pieza,
            cantidad=cantidad,
            precio_unitario=prestacion.precio_base,
            cobertura_item=cobertura_item,
            copago_item=copago_item,
        )
        await uow.items_presupuesto.add(item)
        persistidos.append(item)

    await auditar(
        uow,
        accion="presupuesto.editar",
        entidad="presupuesto",
        entidad_id=presupuesto.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    return presupuesto, persistidos


async def recalcular_presupuesto(
    uow: UnitOfWork,
    provider: CoberturaProvider,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    presupuesto_id: uuid.UUID,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> tuple[Presupuesto, list[ItemPresupuesto]]:
    """Refresh only coverage; the frozen unit prices are never touched (D7)."""
    presupuesto, items = await _cargar_presupuesto(
        uow, consultorio_id, presupuesto_id
    )
    await _exigir_escritura_existente(uow, usuario, presupuesto)
    _exigir_borrador(presupuesto)

    paciente = await _resolver_paciente(
        uow, consultorio_id, presupuesto.paciente_id
    )
    cobertura = await _resolver_cobertura(uow, provider, paciente)

    for item in items:
        prestacion = await uow.prestaciones.get(item.prestacion_id)
        porcentaje = Decimal("0")
        if (
            cobertura is not None
            and prestacion is not None
            and cobertura.cubre(prestacion.codigo)
        ):
            porcentaje = cobertura.cobertura_porcentaje
        cobertura_item, copago_item = calcular_item(
            item.precio_unitario, item.cantidad, porcentaje
        )
        item.cobertura_item = cobertura_item
        item.copago_item = copago_item

    totales = calcular_presupuesto(
        [(item.cobertura_item, item.copago_item) for item in items]
    )
    presupuesto.cobertura_estado = _estado_cobertura(cobertura)
    presupuesto.subtotal = totales.subtotal
    presupuesto.cobertura_calculada = totales.cobertura_calculada
    presupuesto.copago = totales.copago
    await uow.session.flush()
    await uow.session.refresh(presupuesto)

    await auditar(
        uow,
        accion="presupuesto.recalcular",
        entidad="presupuesto",
        entidad_id=presupuesto.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    return presupuesto, items


_ACCIONES_ESTADO = {
    "aceptado": "presupuesto.aceptar",
    "rechazado": "presupuesto.rechazar",
    "en_curso": "presupuesto.en_curso",
    "finalizado": "presupuesto.finalizar",
}


async def cambiar_estado_presupuesto(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    presupuesto_id: uuid.UUID,
    nuevo_estado: str,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> tuple[Presupuesto, list[ItemPresupuesto]]:
    """Apply the D6 matrix; repeating the current state is a silent no-op."""
    presupuesto, items = await _cargar_presupuesto(
        uow, consultorio_id, presupuesto_id
    )
    await _exigir_escritura_existente(uow, usuario, presupuesto)

    if presupuesto.estado == nuevo_estado:
        return presupuesto, items
    if nuevo_estado not in ESTADOS or not puede_transicionar(
        presupuesto.estado, nuevo_estado
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Transición de estado no permitida",
        )

    presupuesto.estado = nuevo_estado
    await uow.session.flush()
    await uow.session.refresh(presupuesto)
    await auditar(
        uow,
        accion=_ACCIONES_ESTADO[nuevo_estado],
        entidad="presupuesto",
        entidad_id=presupuesto.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
    return presupuesto, items


async def eliminar_presupuesto(
    uow: UnitOfWork,
    *,
    consultorio_id: uuid.UUID,
    usuario: Usuario,
    presupuesto_id: uuid.UUID,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> None:
    """Soft delete only a draft; an accepted offer stays as commercial history."""
    presupuesto, _items = await _cargar_presupuesto(
        uow, consultorio_id, presupuesto_id
    )
    await _exigir_escritura_existente(uow, usuario, presupuesto)
    _exigir_borrador(presupuesto)

    await uow.items_presupuesto.desactivar_de_presupuesto(presupuesto.id)
    await uow.presupuestos.soft_delete(presupuesto)
    await auditar(
        uow,
        accion="presupuesto.eliminar",
        entidad="presupuesto",
        entidad_id=presupuesto.id,
        usuario_id=usuario.id,
        ip=ip,
        dispositivo=dispositivo,
    )
