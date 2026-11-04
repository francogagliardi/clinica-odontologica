"""Clinical authorisation and audit helpers (C-11, design D8/D9).

"Own patient" means: a non-deleted turn of that patient with the professional
linked to the authenticated user, in a live state (reservado, confirmado,
en_sala, atendido). Cancelled or no-show turns do not grant clinical access.
"Assisted patient" for the assistant is a turn `en_sala` right now: v1 has no
assistant→professional link, so inventing one would change the RBAC matrix.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import HTTPException, status

from app.domain.turnos import ESTADOS_ACTIVOS
from app.infrastructure import audit
from app.infrastructure.uow import UnitOfWork
from app.models.agenda import Profesional
from app.models.clinica import Evolucion, HallazgoDental, Odontograma
from app.models.security import Usuario

ESTADOS_PROPIOS: tuple[str, ...] = tuple(sorted(ESTADOS_ACTIVOS))
ESTADOS_EN_SALA: tuple[str, ...] = ("en_sala",)

ROLES_LECTURA = frozenset(
    {"administrador", "odontologo", "recepcionista", "asistente", "auditor"}
)
ROLES_LECTURA_TOTAL = frozenset(
    {"administrador", "recepcionista", "auditor"}
)
ROLES_ESCRITURA = frozenset({"odontologo"})


def roles_activos(usuario: Usuario) -> set[str]:
    """Active role names of the authenticated user."""
    return {
        rol.nombre
        for rol in usuario.roles
        if rol.is_active and rol.deleted_at is None
    }


async def paciente_propio(
    uow: UnitOfWork, usuario: Usuario, paciente_id: uuid.UUID
) -> bool:
    """True when the dentist has a live turn with that patient (design D8)."""
    profesional = await uow.profesionales.get_by_usuario(usuario.id)
    if profesional is None:
        return False
    return await uow.turnos.existe_para_paciente(
        paciente_id,
        estados=ESTADOS_PROPIOS,
        profesional_id=profesional.id,
    )


async def paciente_en_sala(
    uow: UnitOfWork, paciente_id: uuid.UUID
) -> bool:
    """True only while the patient has a turn `en_sala` (assistant scope)."""
    return await uow.turnos.existe_para_paciente(
        paciente_id, estados=ESTADOS_EN_SALA
    )


async def puede_leer_historia(
    uow: UnitOfWork, usuario: Usuario, paciente_id: uuid.UUID
) -> bool:
    """Read matrix: admin/reception/auditor all; dentist owns; assistant in-room."""
    roles = roles_activos(usuario)
    if roles & ROLES_LECTURA_TOTAL:
        return True
    if "odontologo" in roles:
        return await paciente_propio(uow, usuario, paciente_id)
    if "asistente" in roles:
        return await paciente_en_sala(uow, paciente_id)
    return False


async def puede_escribir_historia(
    uow: UnitOfWork, usuario: Usuario, paciente_id: uuid.UUID
) -> bool:
    """Write matrix: only a dentist over their own patient (design D8)."""
    if not roles_activos(usuario) & ROLES_ESCRITURA:
        return False
    return await paciente_propio(uow, usuario, paciente_id)


async def profesional_del_usuario(
    uow: UnitOfWork, usuario: Usuario
) -> Profesional | None:
    """Professional row linked to the authenticated dentist, if any."""
    return await uow.profesionales.get_by_usuario(usuario.id)


async def puede_editar_borrador(
    uow: UnitOfWork,
    usuario: Usuario,
    evolucion: Evolucion,
    paciente_id: uuid.UUID,
) -> bool:
    """Draft edits: its dentist author or an assistant with the patient in room."""
    if evolucion.firmada or evolucion.deleted_at is not None:
        return False
    roles = roles_activos(usuario)
    if "odontologo" in roles:
        return (
            evolucion.creado_por == usuario.id
            and await paciente_propio(uow, usuario, paciente_id)
        )
    if "asistente" in roles:
        return await paciente_en_sala(uow, paciente_id)
    return False


async def puede_firmar_evolucion(
    uow: UnitOfWork,
    usuario: Usuario,
    evolucion: Evolucion,
    paciente_id: uuid.UUID,
) -> bool:
    """Only the dentist author signs, and only over a live own patient."""
    if "odontologo" not in roles_activos(usuario):
        return False
    if evolucion.creado_por != usuario.id:
        return False
    return await paciente_propio(uow, usuario, paciente_id)


async def validar_rectificacion(
    uow: UnitOfWork,
    *,
    historia_id: uuid.UUID,
    rectifica_a: uuid.UUID,
) -> Evolucion:
    """Resolve a valid signed target for a correction (design D4/D5).

    Unknown/deleted target → 404; draft or foreign history → 422; an existing
    active correction → 409. The unique partial index backs the last one.
    """
    referencia = await uow.evoluciones.get(rectifica_a)
    if referencia is None or referencia.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evolución a rectificar no encontrada",
        )
    if referencia.historia_id != historia_id or not referencia.firmada:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Solo se rectifica una evolución firmada de la misma "
                "historia clínica"
            ),
        )
    if (
        await uow.evoluciones.get_rectificatoria_activa(referencia.id)
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La evolución ya tiene una rectificatoria activa",
        )
    return referencia


async def crear_version_odontograma(
    uow: UnitOfWork,
    *,
    historia_id: uuid.UUID,
    pieza: int,
    cara: str,
    estado: str,
    diagnostico: str | None,
    cie10: str | None,
    fecha: date | None,
) -> Odontograma:
    """Create a complete snapshot N+1, copying N except the changed face.

    The history row is locked (`FOR UPDATE`) so two concurrent writes serialize
    and never compute the same version (design D6). Previous snapshots are
    never touched; the unique index `(historia_id, version)` is the safety net.
    """
    await uow.historias.get_for_update(historia_id)
    version = await uow.odontogramas.proxima_version(historia_id)
    anterior = await uow.odontogramas.get_vigente(historia_id)

    odontograma = Odontograma(historia_id=historia_id, version=version)
    await uow.odontogramas.add(odontograma)

    if anterior is not None:
        for hallazgo in await uow.hallazgos.list_by_odontograma(anterior.id):
            if hallazgo.pieza == pieza and hallazgo.cara == cara:
                continue
            await uow.hallazgos.add(
                HallazgoDental(
                    odontograma_id=odontograma.id,
                    pieza=hallazgo.pieza,
                    cara=hallazgo.cara,
                    estado=hallazgo.estado,
                    diagnostico=hallazgo.diagnostico,
                    cie10=hallazgo.cie10,
                    fecha=hallazgo.fecha,
                )
            )

    await uow.hallazgos.add(
        HallazgoDental(
            odontograma_id=odontograma.id,
            pieza=pieza,
            cara=cara,
            estado=estado,
            diagnostico=diagnostico,
            cie10=cie10,
            fecha=fecha or date.today(),
        )
    )
    return odontograma


async def auditar(
    uow: UnitOfWork,
    *,
    accion: str,
    entidad: str,
    entidad_id: str | uuid.UUID,
    usuario_id: uuid.UUID | None,
    ip: str | None = None,
    dispositivo: str | None = None,
) -> None:
    """Append one audit row inside the caller's transaction (RN-SE-02)."""
    await audit.registrar(
        uow.session,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        usuario_id=usuario_id,
        ip=ip,
        dispositivo=dispositivo,
    )
