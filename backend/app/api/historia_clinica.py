"""Clinical history endpoints (C-11 slice 1, design D11).

Apertura is the only clinical write in this slice: only a dentist with a live
turn with the patient can open the file, and the aperture is audited in the
same transaction. Reads apply the D8 matrix row by row; the history of another
consultorio is indistinguishable from a missing one (404).
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from starlette.datastructures import UploadFile

from app.api.deps import (
    client_ip,
    dispositivo,
    get_consultorio_demo_id,
    get_uow,
    reject_unexpected_query_except,
    require_role,
)
from app.application.clinica import (
    ROLES_LECTURA,
    auditar,
    puede_editar_borrador,
    puede_escribir_historia,
    puede_firmar_evolucion,
    puede_leer_historia,
    profesional_del_usuario,
    validar_rectificacion,
)
from app.domain import consentimientos
from app.domain.clinica import (
    MAX_ADJUNTO_BYTES,
    extension_peligrosa,
    firma_coincide_con_mime,
    mime_permitido,
    sanear_nombre,
)
from app.infrastructure.uow import UnitOfWork
from app.models.clinica import Adjunto, Consentimiento, Evolucion, HistoriaClinica
from app.models.pacientes import Paciente
from app.models.security import Usuario
from app.schemas.clinica import (
    AdjuntoResponse,
    ConsentimientoCreate,
    ConsentimientoResponse,
    EvolucionCreate,
    EvolucionResponse,
    EvolucionUpdate,
    FirmaRequest,
    HistoriaClinicaCreate,
    HistoriaClinicaResponse,
)

router = APIRouter(tags=["historia-clinica"])

_lectura = require_role(*ROLES_LECTURA)
_escritura = require_role("odontologo")

_HISTORIA_NO_ENCONTRADA = "Historia clínica no encontrada"
_PACIENTE_NO_ENCONTRADO = "Paciente no encontrado"


def _to_response(historia: HistoriaClinica) -> HistoriaClinicaResponse:
    return HistoriaClinicaResponse(
        id=historia.id,
        consultorio_id=historia.consultorio_id,
        paciente_id=historia.paciente_id,
        abierta_por=historia.abierta_por,
        fecha_apertura=historia.fecha_apertura,
        is_active=historia.is_active,
    )


async def _paciente_activo(
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
            detail=_PACIENTE_NO_ENCONTRADO,
        )
    return paciente


async def _historia_activa(
    uow: UnitOfWork,
    consultorio_id: uuid.UUID,
    historia_id: uuid.UUID,
) -> HistoriaClinica:
    historia = await uow.historias.get(historia_id)
    if (
        historia is None
        or historia.consultorio_id != consultorio_id
        or historia.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_HISTORIA_NO_ENCONTRADA,
        )
    return historia


def _es_conflicto_de_unicidad(error: IntegrityError) -> bool:
    original = getattr(error, "orig", error)
    sqlstate = getattr(original, "sqlstate", None) or getattr(
        original, "pgcode", None
    )
    return sqlstate == "23505"


@router.post(
    "/historia-clinica",
    response_model=HistoriaClinicaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Abrir la historia clínica de un paciente propio",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def create_historia_clinica(
    payload: HistoriaClinicaCreate,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> HistoriaClinicaResponse:
    paciente = await _paciente_activo(
        uow, consultorio_id, payload.paciente_id
    )
    if not await puede_escribir_historia(uow, current_user, paciente.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés acceso clínico a este paciente",
        )
    if (
        await uow.historias.get_activa_por_paciente(paciente.id)
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El paciente ya tiene una historia clínica activa",
        )

    historia = HistoriaClinica(
        consultorio_id=consultorio_id,
        paciente_id=paciente.id,
        abierta_por=current_user.id,
    )
    try:
        await uow.historias.add(historia)
    except IntegrityError as error:
        if _es_conflicto_de_unicidad(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El paciente ya tiene una historia clínica activa",
            ) from error
        raise

    await auditar(
        uow,
        accion="historia_clinica.crear",
        entidad="historia_clinica",
        entidad_id=historia.id,
        usuario_id=current_user.id,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_response(historia)


@router.get(
    "/historia-clinica/{historia_id}",
    response_model=HistoriaClinicaResponse,
    summary="Leer una historia clínica por identificador",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def read_historia_clinica(
    historia_id: uuid.UUID,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> HistoriaClinicaResponse:
    historia = await _historia_activa(uow, consultorio_id, historia_id)
    if not await puede_leer_historia(
        uow, current_user, historia.paciente_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés acceso clínico a este paciente",
        )
    return _to_response(historia)


@router.get(
    "/pacientes/{paciente_id}/historia-clinica",
    response_model=HistoriaClinicaResponse,
    summary="Leer la historia clínica activa de un paciente",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def read_historia_por_paciente(
    paciente_id: uuid.UUID,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> HistoriaClinicaResponse:
    paciente = await _paciente_activo(uow, consultorio_id, paciente_id)
    if not await puede_leer_historia(uow, current_user, paciente.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés acceso clínico a este paciente",
        )
    historia = await uow.historias.get_activa_por_paciente(paciente.id)
    if historia is None or historia.consultorio_id != consultorio_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_HISTORIA_NO_ENCONTRADA,
        )
    return _to_response(historia)


async def _exigir_lectura_paciente(
    uow: UnitOfWork, usuario: Usuario, paciente_id: uuid.UUID
) -> None:
    if not await puede_leer_historia(uow, usuario, paciente_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés acceso clínico a este paciente",
        )


async def _exigir_escritura_paciente(
    uow: UnitOfWork, usuario: Usuario, paciente_id: uuid.UUID
) -> None:
    if not await puede_escribir_historia(uow, usuario, paciente_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés acceso clínico a este paciente",
        )


async def _evolucion_de_historia(
    uow: UnitOfWork, historia_id: uuid.UUID, evolucion_id: uuid.UUID
) -> Evolucion:
    evolucion = await uow.evoluciones.get(evolucion_id)
    if (
        evolucion is None
        or evolucion.historia_id != historia_id
        or evolucion.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evolución no encontrada",
        )
    return evolucion


async def _rectificada_por(
    uow: UnitOfWork, evolucion: Evolucion
) -> uuid.UUID | None:
    rectificatoria = await uow.evoluciones.get_rectificatoria_activa(
        evolucion.id
    )
    if rectificatoria is None or not rectificatoria.firmada:
        return None
    return rectificatoria.id


async def _to_evolucion_response(
    uow: UnitOfWork,
    evolucion: Evolucion,
    rectificada_por: uuid.UUID | None = None,
) -> EvolucionResponse:
    return EvolucionResponse(
        id=evolucion.id,
        historia_id=evolucion.historia_id,
        profesional_id=evolucion.profesional_id,
        creado_por=evolucion.creado_por,
        fecha=evolucion.fecha,
        texto=evolucion.texto,
        firmada=evolucion.firmada,
        firmada_por=evolucion.firmada_por,
        fecha_firma=evolucion.fecha_firma,
        rectifica_a=evolucion.rectifica_a,
        rectificada_por=(
            rectificada_por
            if rectificada_por is not None
            else await _rectificada_por(uow, evolucion)
        ),
        is_active=evolucion.is_active,
    )


def _to_adjunto_response(adjunto: Adjunto) -> AdjuntoResponse:
    return AdjuntoResponse(
        id=adjunto.id,
        historia_id=adjunto.historia_id,
        nombre=adjunto.nombre,
        mime=adjunto.mime,
        tamano=adjunto.tamano,
        subido_por=adjunto.subido_por,
        created_at=adjunto.created_at,
        is_active=adjunto.is_active,
    )


def _to_consentimiento_response(
    consentimiento: Consentimiento,
) -> ConsentimientoResponse:
    return ConsentimientoResponse(
        id=consentimiento.id,
        consultorio_id=consentimiento.consultorio_id,
        paciente_id=consentimiento.paciente_id,
        tipo=consentimiento.tipo,
        texto_version=consentimiento.texto_version,
        texto_hash=consentimiento.texto_hash,
        firma_ref=consentimiento.firma_ref,
        fecha=consentimiento.fecha,
        registrado_por=consentimiento.registrado_por,
        is_active=consentimiento.is_active,
    )


@router.get(
    "/historia-clinica/{historia_id}/evoluciones",
    response_model=list[EvolucionResponse],
    summary="Listar evoluciones de una historia (descendente)",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def list_evoluciones(
    historia_id: uuid.UUID,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> list[EvolucionResponse]:
    historia = await _historia_activa(uow, consultorio_id, historia_id)
    await _exigir_lectura_paciente(uow, current_user, historia.paciente_id)
    evoluciones = await uow.evoluciones.list_by_historia(historia.id)
    firmadas = {
        evolucion.rectifica_a: evolucion.id
        for evolucion in evoluciones
        if evolucion.rectifica_a is not None and evolucion.firmada
    }
    return [
        await _to_evolucion_response(
            uow, evolucion, firmadas.get(evolucion.id)
        )
        for evolucion in evoluciones
    ]


@router.post(
    "/historia-clinica/{historia_id}/evoluciones",
    response_model=EvolucionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una evolución en borrador (o su rectificatoria)",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def create_evolucion(
    historia_id: uuid.UUID,
    payload: EvolucionCreate,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> EvolucionResponse:
    historia = await _historia_activa(uow, consultorio_id, historia_id)
    await _exigir_escritura_paciente(uow, current_user, historia.paciente_id)
    profesional = await profesional_del_usuario(uow, current_user)
    if profesional is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene un profesional vinculado",
        )

    if payload.rectifica_a is not None:
        await validar_rectificacion(
            uow,
            historia_id=historia.id,
            rectifica_a=payload.rectifica_a,
        )

    evolucion = Evolucion(
        historia_id=historia.id,
        profesional_id=profesional.id,
        creado_por=current_user.id,
        fecha=datetime.now(timezone.utc),
        texto=payload.texto,
        rectifica_a=payload.rectifica_a,
    )
    try:
        await uow.evoluciones.add(evolucion)
    except IntegrityError as error:
        if _es_conflicto_de_unicidad(error):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La evolución ya tiene una rectificatoria activa",
            ) from error
        raise

    await auditar(
        uow,
        accion=(
            "evolucion.rectificar"
            if payload.rectifica_a is not None
            else "evolucion.crear"
        ),
        entidad="evolucion",
        entidad_id=evolucion.id,
        usuario_id=current_user.id,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return await _to_evolucion_response(uow, evolucion, None)


@router.get(
    "/historia-clinica/{historia_id}/evoluciones/{evolucion_id}",
    response_model=EvolucionResponse,
    summary="Leer una evolución de la historia",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def read_evolucion(
    historia_id: uuid.UUID,
    evolucion_id: uuid.UUID,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> EvolucionResponse:
    historia = await _historia_activa(uow, consultorio_id, historia_id)
    await _exigir_lectura_paciente(uow, current_user, historia.paciente_id)
    evolucion = await _evolucion_de_historia(uow, historia.id, evolucion_id)
    return await _to_evolucion_response(uow, evolucion)


@router.put(
    "/historia-clinica/{historia_id}/evoluciones/{evolucion_id}",
    response_model=EvolucionResponse,
    summary="Editar el texto de un borrador",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def update_evolucion(
    historia_id: uuid.UUID,
    evolucion_id: uuid.UUID,
    payload: EvolucionUpdate,
    request: Request,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> EvolucionResponse:
    historia = await _historia_activa(uow, consultorio_id, historia_id)
    evolucion = await _evolucion_de_historia(uow, historia.id, evolucion_id)
    if evolucion.firmada:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La evolución firmada es inmutable",
        )
    if not await puede_editar_borrador(
        uow, current_user, evolucion, historia.paciente_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés permiso para editar este borrador",
        )

    evolucion.texto = payload.texto
    await uow.session.flush()
    await auditar(
        uow,
        accion="evolucion.editar",
        entidad="evolucion",
        entidad_id=evolucion.id,
        usuario_id=current_user.id,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return await _to_evolucion_response(uow, evolucion)


@router.delete(
    "/historia-clinica/{historia_id}/evoluciones/{evolucion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Descartar un borrador (baja lógica)",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def delete_evolucion(
    historia_id: uuid.UUID,
    evolucion_id: uuid.UUID,
    request: Request,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> Response:
    historia = await _historia_activa(uow, consultorio_id, historia_id)
    evolucion = await _evolucion_de_historia(uow, historia.id, evolucion_id)
    if evolucion.firmada:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La evolución firmada es inmutable",
        )
    if not await puede_editar_borrador(
        uow, current_user, evolucion, historia.paciente_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés permiso para descartar este borrador",
        )

    await uow.evoluciones.soft_delete(evolucion)
    await auditar(
        uow,
        accion="evolucion.descartar",
        entidad="evolucion",
        entidad_id=evolucion.id,
        usuario_id=current_user.id,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/historia-clinica/{historia_id}/evoluciones/{evolucion_id}/firmar",
    response_model=EvolucionResponse,
    summary="Firmar una evolución en borrador (idempotente)",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def sign_evolucion(
    historia_id: uuid.UUID,
    evolucion_id: uuid.UUID,
    payload: FirmaRequest,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> EvolucionResponse:
    historia = await _historia_activa(uow, consultorio_id, historia_id)
    evolucion = await _evolucion_de_historia(uow, historia.id, evolucion_id)
    if not await puede_firmar_evolucion(
        uow, current_user, evolucion, historia.paciente_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el odontólogo autor puede firmar la evolución",
        )
    if evolucion.firmada:
        return await _to_evolucion_response(uow, evolucion)

    evolucion.firmada = True
    evolucion.firmada_por = current_user.id
    evolucion.fecha_firma = datetime.now(timezone.utc)
    await uow.session.flush()
    await auditar(
        uow,
        accion="evolucion.firmar",
        entidad="evolucion",
        entidad_id=evolucion.id,
        usuario_id=current_user.id,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return await _to_evolucion_response(uow, evolucion)


@router.post(
    "/adjuntos",
    response_model=AdjuntoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subir un adjunto clínico (multipart, máximo 5 MB)",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def create_adjunto(
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> AdjuntoResponse:
    form = await request.form()
    if set(form.keys()) != {"historia_id", "archivo"}:
        raise HTTPException(
            status_code=422,
            detail="El multipart debe tener solo historia_id y archivo",
        )
    historia_raw = form.get("historia_id")
    archivo = form.get("archivo")
    if not isinstance(historia_raw, str) or not isinstance(
        archivo, UploadFile
    ):
        raise HTTPException(
            status_code=422,
            detail="Falta historia_id o el archivo",
        )
    try:
        historia_id = uuid.UUID(historia_raw)
    except ValueError as error:
        raise HTTPException(
            status_code=422, detail="historia_id no es un UUID válido"
        ) from error

    historia = await _historia_activa(uow, consultorio_id, historia_id)
    await _exigir_escritura_paciente(uow, current_user, historia.paciente_id)

    contenido = await archivo.read(MAX_ADJUNTO_BYTES + 1)
    if len(contenido) > MAX_ADJUNTO_BYTES:
        raise HTTPException(
            status_code=422,
            detail="El adjunto supera el máximo de 5 MB",
        )
    if not contenido:
        raise HTTPException(status_code=422, detail="El archivo está vacío")

    mime = (archivo.content_type or "").split(";")[0].strip().lower()
    if not mime_permitido(mime):
        raise HTTPException(
            status_code=422,
            detail="Tipo de archivo no permitido",
        )
    nombre = sanear_nombre(archivo.filename or "")
    if extension_peligrosa(nombre):
        raise HTTPException(
            status_code=422,
            detail="Extensión de archivo no permitida",
        )
    if not firma_coincide_con_mime(mime, contenido):
        raise HTTPException(
            status_code=422,
            detail="El contenido no coincide con el tipo declarado",
        )

    adjunto = Adjunto(
        historia_id=historia.id,
        nombre=nombre,
        mime=mime,
        tamano=len(contenido),
        contenido=contenido,
        subido_por=current_user.id,
    )
    await uow.adjuntos.add(adjunto)
    await auditar(
        uow,
        accion="adjunto.crear",
        entidad="adjunto",
        entidad_id=adjunto.id,
        usuario_id=current_user.id,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_adjunto_response(adjunto)


@router.get(
    "/historia-clinica/{historia_id}/adjuntos",
    response_model=list[AdjuntoResponse],
    summary="Listar metadata de adjuntos de una historia",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def list_adjuntos(
    historia_id: uuid.UUID,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> list[AdjuntoResponse]:
    historia = await _historia_activa(uow, consultorio_id, historia_id)
    await _exigir_lectura_paciente(uow, current_user, historia.paciente_id)
    adjuntos = await uow.adjuntos.list_by_historia(historia.id)
    return [_to_adjunto_response(adjunto) for adjunto in adjuntos]


@router.get(
    "/adjuntos/{adjunto_id}",
    summary="Descargar un adjunto clínico autenticado",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def download_adjunto(
    adjunto_id: uuid.UUID,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> Response:
    adjunto = await uow.adjuntos.get(adjunto_id)
    if adjunto is None or adjunto.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Adjunto no encontrado",
        )
    historia = await uow.historias.get(adjunto.historia_id)
    if (
        historia is None
        or historia.consultorio_id != consultorio_id
        or historia.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Adjunto no encontrado",
        )
    await _exigir_lectura_paciente(uow, current_user, historia.paciente_id)

    nombre = adjunto.nombre.replace('"', "").replace("\\", "").replace("/", "")
    return Response(
        content=adjunto.contenido,
        media_type=adjunto.mime,
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/pacientes/{paciente_id}/consentimientos",
    response_model=ConsentimientoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un consentimiento informado versionado",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def create_consentimiento(
    paciente_id: uuid.UUID,
    payload: ConsentimientoCreate,
    request: Request,
    current_user: Annotated[Usuario, Depends(_escritura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> ConsentimientoResponse:
    paciente = await _paciente_activo(uow, consultorio_id, paciente_id)
    await _exigir_escritura_paciente(uow, current_user, paciente.id)

    fecha = datetime.now(timezone.utc)
    texto_hash, firma_ref = consentimientos.calcular_hashes(
        version=payload.texto_version,
        paciente_id=paciente.id,
        fecha=fecha,
    )
    consentimiento = Consentimiento(
        consultorio_id=consultorio_id,
        paciente_id=paciente.id,
        tipo=payload.tipo,
        texto_version=payload.texto_version,
        texto_hash=texto_hash,
        firma_ref=firma_ref,
        fecha=fecha,
        registrado_por=current_user.id,
    )
    await uow.consentimientos.add(consentimiento)
    await auditar(
        uow,
        accion="consentimiento.registrar",
        entidad="consentimiento",
        entidad_id=consentimiento.id,
        usuario_id=current_user.id,
        ip=client_ip(request),
        dispositivo=dispositivo(request),
    )
    return _to_consentimiento_response(consentimiento)


@router.get(
    "/pacientes/{paciente_id}/consentimientos",
    response_model=list[ConsentimientoResponse],
    summary="Listar consentimientos del paciente (descendente)",
    dependencies=[Depends(reject_unexpected_query_except())],
)
async def list_consentimientos(
    paciente_id: uuid.UUID,
    current_user: Annotated[Usuario, Depends(_lectura)],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    consultorio_id: Annotated[uuid.UUID, Depends(get_consultorio_demo_id)],
) -> list[ConsentimientoResponse]:
    paciente = await _paciente_activo(uow, consultorio_id, paciente_id)
    await _exigir_lectura_paciente(uow, current_user, paciente.id)
    consentimientos_paciente = await uow.consentimientos.list_by_paciente(
        paciente.id
    )
    return [
        _to_consentimiento_response(consentimiento)
        for consentimiento in consentimientos_paciente
    ]
