"""C-15 exportation content, privacy and limits (tasks 7.1-7.5).

The worker generates the ZIP from PostgreSQL; these tests inspect the real
artifact: every canonical entity, manifest counts equal to JSON/CSV, the 2 MB
attachment as binary, the PDF summary, the exclusion of secrets and the two
limits that turn a job into `fallida` without a partial artifact.
"""

import uuid

from app.domain.exportacion import ENTIDADES_EXPORTABLES
from app.application.exportaciones import procesar_exportacion
from tests.integration.exportaciones_helpers import (
    ADJUNTO_BYTES,
    ADJUNTO_NOMBRE,
    AHORA,
    SECRETO_CLAIM,
    SECRETO_LINK,
    SECRETO_MENSAJE,
    SECRETO_PAYLOAD,
    SECRETO_PREFERENCIA,
    SECRETO_PROVEEDOR,
    SECRETO_RESPUESTA,
    SECRETO_TOKEN,
    SECRETO_WA,
    config_exportacion,
    crear_paciente_vacio,
    datos_json,
    filas_csv,
    leer_exportacion,
    manifiesto_json,
    setup_exportacion_completa,
    textos_del_zip,
    unzip,
)
from tests.integration.helpers import run
from tests.integration.reportes_helpers import insertar_exportacion_db


def _exportar(session_factory, data, *, alcance="paciente", paciente_id=None, **config):
    exportacion_id = run(
        insertar_exportacion_db(
            session_factory,
            consultorio_id=data["consultorio_id"],
            solicitado_por=data["actores"]["administrador"].id,
            alcance=alcance,
            paciente_id=paciente_id,
        )
    )
    return exportacion_id, run(
        procesar_exportacion(
            session_factory,
            exportacion_id,
            config=config_exportacion(**config),
            ahora=AHORA,
        )
    )


def test_zip_contiene_entidades_conteos_coherentes_adjunto_y_pdf(
    session_factory,
) -> None:
    data = run(setup_exportacion_completa(session_factory))
    _exportacion_id, fila = _exportar(
        session_factory, data, paciente_id=data["paciente"].id
    )
    assert fila is not None
    assert fila.estado == "lista", fila.ultimo_error
    assert fila.contenido is not None
    assert fila.tamano_bytes == len(fila.contenido)
    assert fila.generada_at is not None

    entradas = unzip(fila.contenido)
    assert {"exportacion.pdf", "datos.json", "manifiesto.json"} <= set(
        entradas
    )
    assert entradas["exportacion.pdf"].startswith(b"%PDF-")
    for entidad in ENTIDADES_EXPORTABLES:
        assert f"csv/{entidad}.csv" in entradas, entidad

    datos = datos_json(fila.contenido)
    manifiesto = manifiesto_json(fila.contenido)
    conteos = {
        entidad["nombre"]: entidad["filas"]
        for entidad in manifiesto["entidades"]
    }
    for entidad in ENTIDADES_EXPORTABLES:
        assert entidad in datos
        assert conteos[entidad] == len(datos[entidad])
        assert conteos[entidad] == len(
            filas_csv(fila.contenido, entidad)
        )

    adjuntos = [
        nombre for nombre in entradas if nombre.startswith("adjuntos/")
    ]
    assert len(adjuntos) == 1
    assert adjuntos[0].startswith(f"adjuntos/{data['adjunto_id']}_")
    assert entradas[adjuntos[0]] == ADJUNTO_BYTES
    assert datos["adjuntos"][0]["nombre"] == ADJUNTO_NOMBRE
    assert "contenido" not in datos["adjuntos"][0]

    assert manifiesto["total_filas"] == sum(conteos.values())
    assert "exclusiones" in manifiesto
    assert manifiesto["alcance"] == "paciente"
    for entidad in (
        "recordatorios",
        "mensajes_whatsapp",
        "liquidaciones_obras_sociales",
        "items_liquidacion",
        "registro_auditoria",
    ):
        assert conteos[entidad] >= 1, entidad
        assert len(datos[entidad]) >= 1, entidad


def test_exportacion_de_consultorio_no_incluye_otro_tenant(
    session_factory,
) -> None:
    from tests.integration.clinica_helpers import otro_consultorio

    data = run(setup_exportacion_completa(session_factory))
    ajeno = run(otro_consultorio(session_factory))
    _exportacion_id, fila = _exportar(
        session_factory, data, alcance="consultorio"
    )
    assert fila is not None and fila.estado == "lista", fila.ultimo_error

    datos = datos_json(fila.contenido)
    ids = {fila["id"] for fila in datos["pacientes"]}
    assert str(ajeno["paciente_id"]) not in ids
    assert all(
        fila["consultorio_id"] != str(ajeno["consultorio_id"])
        for fila in datos["pacientes"]
    )


def test_paciente_sin_datos_clinicos_exporta_secciones_vacias(
    session_factory,
) -> None:
    data = run(setup_exportacion_completa(session_factory))
    paciente_id = run(
        crear_paciente_vacio(
            session_factory, data["consultorio_id"]
        )
    )
    _exportacion_id, fila = _exportar(
        session_factory, data, paciente_id=paciente_id
    )
    assert fila is not None and fila.estado == "lista", fila.ultimo_error

    datos = datos_json(fila.contenido)
    manifiesto = manifiesto_json(fila.contenido)
    conteos = {
        entidad["nombre"]: entidad["filas"]
        for entidad in manifiesto["entidades"]
    }
    for entidad in (
        "historias_clinicas",
        "evoluciones",
        "odontogramas",
        "hallazgos_dentales",
        "adjuntos",
        "consentimientos",
        "presupuestos",
        "cobros",
        "comprobantes",
    ):
        assert datos[entidad] == [], entidad
        assert conteos[entidad] == 0, entidad
    assert fila.contenido is not None
    assert unzip(fila.contenido)["exportacion.pdf"].startswith(b"%PDF-")


def test_secretos_ausentes_y_directorio_de_usuarios_sin_hash(
    session_factory,
) -> None:
    data = run(setup_exportacion_completa(session_factory))
    _exportacion_id, fila = _exportar(
        session_factory, data, alcance="consultorio"
    )
    assert fila is not None and fila.estado == "lista", fila.ultimo_error

    textos = textos_del_zip(fila.contenido)
    completo = "\n".join(textos.values())
    for secreto in (
        SECRETO_TOKEN,
        SECRETO_LINK,
        SECRETO_PROVEEDOR,
        SECRETO_PREFERENCIA,
        str(SECRETO_CLAIM),
        SECRETO_PAYLOAD,
        SECRETO_RESPUESTA,
        SECRETO_MENSAJE,
        SECRETO_WA,
        data["actores"]["administrador"].hash_password,
    ):
        assert secreto not in completo

    datos = datos_json(fila.contenido)
    assert "hash_password" not in datos["usuarios"][0]
    assert set(datos["usuarios"][0]) == {"id", "nombre", "email", "roles"}
    assert "token_publico" not in datos["turnos"][0]
    for cobro in datos["cobros"]:
        assert "link_pago" not in cobro
        assert "proveedor_pago_id" not in cobro
        assert "proveedor_preferencia_id" not in cobro
    for comprobante in datos["comprobantes"]:
        assert "claim_token" not in comprobante
        assert "payload_envio" not in comprobante
        assert "respuesta_proveedor" not in comprobante
    for mensaje in datos["mensajes_whatsapp"]:
        assert "payload" not in mensaje
        assert "proveedor_mensaje_id" not in mensaje
    for envio in datos["comprobantes_envios"]:
        assert "proveedor_mensaje_id" not in envio
    for adjunto in datos["adjuntos"]:
        assert "contenido" not in adjunto

    comprobantes = filas_csv(fila.contenido, "comprobantes")
    assert comprobantes[0]["cae"]
    assert comprobantes[0]["qr_fiscal"].startswith(
        "https://www.afip.gob.ar"
    )

    usuarios = filas_csv(fila.contenido, "usuarios")
    assert usuarios
    assert list(usuarios[0]) == ["id", "nombre", "email", "roles"]
    roles = " ".join(fila["roles"] for fila in usuarios)
    assert "administrador" in roles
    assert "odontologo" in roles


def test_limite_de_filas_deja_fallida_sin_artefacto(session_factory) -> None:
    data = run(setup_exportacion_completa(session_factory))
    exportacion_id, fila = _exportar(
        session_factory, data, alcance="consultorio", max_filas=1
    )
    assert fila is not None
    assert fila.estado == "fallida"
    assert fila.ultimo_error is not None
    assert "limite_excedido:" in fila.ultimo_error
    assert "pacientes" in fila.ultimo_error
    assert fila.contenido is None
    assert fila.tamano_bytes is None
    assert fila.generada_at is None
    guardada = run(leer_exportacion(session_factory, exportacion_id))
    assert guardada is not None and guardada.contenido is None


def test_limite_de_bytes_deja_fallida_sin_artefacto(session_factory) -> None:
    data = run(setup_exportacion_completa(session_factory))
    exportacion_id, fila = _exportar(
        session_factory, data, alcance="consultorio", max_bytes=1
    )
    assert fila is not None
    assert fila.estado == "fallida"
    assert fila.ultimo_error is not None
    assert "limite_excedido:" in fila.ultimo_error
    assert "tamano_bytes" in fila.ultimo_error
    assert fila.contenido is None
    guardada = run(leer_exportacion(session_factory, exportacion_id))
    assert guardada is not None and guardada.contenido is None
