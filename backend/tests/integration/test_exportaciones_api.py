"""C-15 exportation API: request, idempotency, state and download (8.1-8.4)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, text

from app.api.deps import get_redis
from app.application.exportaciones import procesar_exportacion
from app.main import app
from app.models import Exportacion
from tests.integration.clinica_helpers import auditorias
from tests.integration.comprobantes_helpers import FakeRedis
from tests.integration.exportaciones_helpers import AHORA, config_exportacion
from tests.integration.helpers import run
from tests.integration.pacientes_helpers import create_paciente
from tests.integration.recursos_helpers import bearer
from tests.integration.reportes_helpers import (
    insertar_exportacion_db,
    setup_exportaciones,
)

PACIENTE_URL = "/exportaciones"


def _setup(session_factory):
    return run(setup_exportaciones(session_factory))


def _post(api_client, data, payload, actor="administrador", **kwargs):
    headers = bearer(data["actores"][actor])
    user_agent = kwargs.pop("user_agent", None)
    if user_agent is not None:
        headers["User-Agent"] = user_agent
    return api_client.post(
        PACIENTE_URL, json=payload, headers=headers, **kwargs
    )


def _get(api_client, data, path, actor="administrador", **kwargs):
    return api_client.get(
        path, headers=bearer(data["actores"][actor]), **kwargs
    )


def _contar(session_factory) -> int:
    async def contar() -> int:
        async with session_factory() as session:
            return int(
                await session.scalar(
                    select(func.count()).select_from(Exportacion)
                )
                or 0
            )

    return run(contar())


def test_paciente_202_pendiente_y_estado(api_client, session_factory) -> None:
    data = _setup(session_factory)
    paciente_id = data["paciente"].id

    respuesta = _post(
        api_client,
        data,
        {"alcance": "paciente", "paciente_id": str(paciente_id)},
        user_agent="pytest-ua-c15",
    )
    assert respuesta.status_code == 202, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["alcance"] == "paciente"
    assert cuerpo["paciente_id"] == str(paciente_id)
    assert cuerpo["solicitado_por"] == str(data["actores"]["administrador"].id)
    assert cuerpo["estado"] == "pendiente"
    assert cuerpo["tamano_bytes"] is None
    assert cuerpo["generada_at"] is None

    estado = _get(api_client, data, f"/exportaciones/{cuerpo['id']}")
    assert estado.status_code == 200, estado.text
    assert estado.json()["id"] == cuerpo["id"]


def test_paciente_inexistente_inactivo_o_ajeno_404(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)

    inexistente = _post(
        api_client,
        data,
        {"alcance": "paciente", "paciente_id": str(uuid.uuid4())},
    )
    assert inexistente.status_code == 404, inexistente.text

    inactivo = run(
        create_paciente(
            session_factory,
            data["consultorio_id"],
            nombre="Inactivo",
            apellido="Api",
            dni="42777111",
            telefono="+5491177772111",
        )
    )

    async def desactivar() -> None:
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "UPDATE pacientes SET is_active = false, "
                    "deleted_at = now() WHERE id = :id"
                ),
                {"id": inactivo.id},
            )

    run(desactivar())
    respuesta_inactivo = _post(
        api_client,
        data,
        {"alcance": "paciente", "paciente_id": str(inactivo.id)},
    )
    assert respuesta_inactivo.status_code == 404, respuesta_inactivo.text

    from tests.integration.clinica_helpers import otro_consultorio

    ajeno = run(otro_consultorio(session_factory))
    respuesta_ajeno = _post(
        api_client,
        data,
        {"alcance": "paciente", "paciente_id": str(ajeno["paciente_id"])},
    )
    assert respuesta_ajeno.status_code == 404, respuesta_ajeno.text


def test_alcance_invalido_campo_extra_y_consultorio_con_paciente_422(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)

    invalido = _post(
        api_client, data, {"alcance": "historias"}
    )
    assert invalido.status_code == 422, invalido.text

    extra = _post(
        api_client,
        data,
        {
            "alcance": "paciente",
            "paciente_id": str(data["paciente"].id),
            "formato": "zip",
        },
    )
    assert extra.status_code == 422, extra.text

    incoherente = _post(
        api_client,
        data,
        {
            "alcance": "consultorio",
            "paciente_id": str(data["paciente"].id),
        },
    )
    assert incoherente.status_code == 422, incoherente.text


def test_consultorio_202_sin_paciente(api_client, session_factory) -> None:
    data = _setup(session_factory)
    respuesta = _post(api_client, data, {"alcance": "consultorio"})
    assert respuesta.status_code == 202, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["alcance"] == "consultorio"
    assert cuerpo["paciente_id"] is None


def test_estado_de_otro_consultorio_404(api_client, session_factory) -> None:
    data = _setup(session_factory)
    from tests.integration.clinica_helpers import otro_consultorio

    otro = run(otro_consultorio(session_factory))
    ajeno_id = run(
        insertar_exportacion_db(
            session_factory,
            consultorio_id=otro["consultorio_id"],
            solicitado_por=data["actores"]["administrador"].id,
            alcance="consultorio",
        )
    )
    respuesta = _get(api_client, data, f"/exportaciones/{ajeno_id}")
    assert respuesta.status_code == 404, respuesta.text
    assert "alcance" not in respuesta.text


def test_idempotencia_en_curso_y_un_solo_job(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    redis = FakeRedis()
    app.dependency_overrides[get_redis] = lambda: redis

    payload = {
        "alcance": "paciente",
        "paciente_id": str(data["paciente"].id),
    }
    primero = _post(api_client, data, payload)
    segundo = _post(api_client, data, payload)
    assert primero.status_code == 202
    assert segundo.status_code == 202
    assert primero.json()["id"] == segundo.json()["id"]
    assert _contar(session_factory) == 1
    assert len(redis.items) == 1
    assert redis.items[0][0] == "reportes:generar"


def test_descarga_lista_y_409_antes_de_tiempo(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    exportacion_id = run(
        insertar_exportacion_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            solicitado_por=data["actores"]["administrador"].id,
            alcance="consultorio",
        )
    )

    pendiente = _get(
        api_client, data, f"/exportaciones/{exportacion_id}/archivo"
    )
    assert pendiente.status_code == 409, pendiente.text

    async def marcar_lista() -> None:
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "UPDATE exportaciones SET estado = 'lista', "
                    "contenido = :contenido, tamano_bytes = :tamano, "
                    "generada_at = :generada WHERE id = :id"
                ),
                {
                    "contenido": b"PK-zip-prueba",
                    "tamano": 13,
                    "generada": AHORA,
                    "id": exportacion_id,
                },
            )

    run(marcar_lista())
    lista = _get(
        api_client, data, f"/exportaciones/{exportacion_id}/archivo"
    )
    assert lista.status_code == 200, lista.text
    assert lista.headers["content-type"] == "application/zip"
    assert lista.content == b"PK-zip-prueba"
    assert "attachment" in lista.headers["content-disposition"]

    async def marcar_fallida() -> None:
        async with session_factory() as session, session.begin():
            await session.execute(
                text(
                    "UPDATE exportaciones SET estado = 'fallida', "
                    "contenido = NULL, tamano_bytes = NULL, "
                    "generada_at = NULL, "
                    "ultimo_error = 'limite_excedido:turnos' "
                    "WHERE id = :id"
                ),
                {"id": exportacion_id},
            )

    run(marcar_fallida())
    fallida = _get(
        api_client, data, f"/exportaciones/{exportacion_id}/archivo"
    )
    assert fallida.status_code == 409, fallida.text
    assert "limite_excedido:turnos" in fallida.text


def test_nueva_exportacion_tras_lista_o_fallida(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    payload = {
        "alcance": "paciente",
        "paciente_id": str(data["paciente"].id),
    }
    primero = _post(api_client, data, payload)
    assert primero.status_code == 202
    exportacion_id = primero.json()["id"]
    async def cerrar(estado: str) -> None:
        async with session_factory() as session, session.begin():
            if estado == "lista":
                await session.execute(
                    text(
                        "UPDATE exportaciones SET estado = 'lista', "
                        "contenido = :contenido, tamano_bytes = :tamano, "
                        "generada_at = :generada, ultimo_error = NULL "
                        "WHERE id = :id"
                    ),
                    {
                        "contenido": b"PK",
                        "tamano": 2,
                        "generada": datetime.now(timezone.utc),
                        "id": exportacion_id,
                    },
                )
            else:
                await session.execute(
                    text(
                        "UPDATE exportaciones SET estado = 'fallida', "
                        "contenido = NULL, tamano_bytes = NULL, "
                        "generada_at = NULL, ultimo_error = 'fallo de prueba' "
                        "WHERE id = :id"
                    ),
                    {"id": exportacion_id},
                )

    for estado in ("lista", "fallida"):
        run(cerrar(estado))
        nueva = _post(api_client, data, payload)
        assert nueva.status_code == 202, nueva.text
        assert nueva.json()["id"] != exportacion_id
        exportacion_id = nueva.json()["id"]


def test_auditoria_solicitar_generar_y_descargar(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    creada = _post(
        api_client,
        data,
        {
            "alcance": "paciente",
            "paciente_id": str(data["paciente"].id),
        },
        user_agent="pytest-ua-c15-audit",
    )
    assert creada.status_code == 202, creada.text
    exportacion_id = uuid.UUID(creada.json()["id"])

    solicitar = run(auditorias(session_factory, "exportacion.solicitar"))
    assert len(solicitar) == 1
    assert solicitar[0].usuario_id == data["actores"]["administrador"].id
    assert solicitar[0].entidad_id == str(exportacion_id)
    assert solicitar[0].dispositivo == "pytest-ua-c15-audit"

    # Polling the state never duplicates audit rows.
    for _ in range(5):
        assert _get(
            api_client, data, f"/exportaciones/{exportacion_id}"
        ).status_code == 200
    assert len(
        run(auditorias(session_factory, "exportacion.solicitar"))
    ) == 1

    fila = run(
        procesar_exportacion(
            session_factory,
            exportacion_id,
            config=config_exportacion(),
            ahora=AHORA,
        )
    )
    assert fila is not None and fila.estado == "lista"
    generar = run(auditorias(session_factory, "exportacion.generar"))
    assert len(generar) == 1
    assert generar[0].usuario_id is None

    archivo = _get(
        api_client, data, f"/exportaciones/{exportacion_id}/archivo"
    )
    assert archivo.status_code == 200
    descargar = run(auditorias(session_factory, "exportacion.descargar"))
    assert len(descargar) == 1
    assert descargar[0].usuario_id == data["actores"]["administrador"].id


def test_solicitud_rechazada_no_deja_auditoria(
    api_client, session_factory
) -> None:
    data = _setup(session_factory)
    antes = run(auditorias(session_factory, "exportacion.solicitar"))
    respuesta = _post(
        api_client,
        data,
        {"alcance": "paciente", "paciente_id": str(uuid.uuid4())},
    )
    assert respuesta.status_code == 404
    despues = run(auditorias(session_factory, "exportacion.solicitar"))
    assert despues == antes
