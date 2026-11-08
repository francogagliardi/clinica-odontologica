"""ZIP artifact contract: names, sanitization, manifest and the PDF summary.

The PDF is generated with `fpdf2` and inspected as bytes: the test asserts the
signature, at least one page and the explicit truncation notice when a section
exceeds the 500-row summary limit (design D4/D5).
"""

import re
import uuid
from datetime import datetime, timezone

from app.domain.exportacion import (
    CAMPOS_EXCLUIDOS,
    ENTIDADES_EXPORTABLES,
    MAX_FILAS_PDF,
    NOMBRE_DATOS,
    NOMBRE_MANIFIESTO,
    NOMBRE_PDF,
    construir_manifiesto,
    nombre_adjunto,
    nombre_csv,
    sanear_nombre_adjunto,
)
from app.infrastructure.exportacion import generar_pdf_resumen

EXPORTACION_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")
GENERADO_EN = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def _paginas(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", pdf))


def test_nombres_fijos_del_zip() -> None:
    assert NOMBRE_PDF == "exportacion.pdf"
    assert NOMBRE_DATOS == "datos.json"
    assert NOMBRE_MANIFIESTO == "manifiesto.json"
    assert MAX_FILAS_PDF == 500


def test_un_csv_por_entidad() -> None:
    assert nombre_csv("turnos") == "csv/turnos.csv"
    assert nombre_csv("items_presupuesto") == "csv/items_presupuesto.csv"


def test_entidades_exportables_incluyen_el_universo_del_erd() -> None:
    esperadas = {
        "pacientes",
        "obras_sociales",
        "turnos",
        "historias_clinicas",
        "evoluciones",
        "odontogramas",
        "hallazgos_dentales",
        "adjuntos",
        "consentimientos",
        "presupuestos",
        "items_presupuesto",
        "prestaciones",
        "cobros",
        "cajas_diarias",
        "movimientos_caja",
        "comprobantes",
        "comprobantes_envios",
        "liquidaciones_obras_sociales",
        "items_liquidacion",
        "recordatorios",
        "mensajes_whatsapp",
        "entradas_lista_espera",
        "registro_auditoria",
        "usuarios",
    }
    assert esperadas == set(ENTIDADES_EXPORTABLES)
    assert len(ENTIDADES_EXPORTABLES) == len(set(ENTIDADES_EXPORTABLES))


def test_saneo_de_nombres_de_adjuntos() -> None:
    traversal = sanear_nombre_adjunto("../../etc/passwd")
    assert "/" not in traversal
    assert "\\" not in traversal
    assert ".." not in traversal
    assert "passwd" in traversal

    con_espacios = sanear_nombre_adjunto("mi foto (1).PDF")
    assert " " not in con_espacios
    assert "(" not in con_espacios
    assert con_espacios.endswith(".PDF")

    assert sanear_nombre_adjunto("") == "adjunto"
    assert sanear_nombre_adjunto("..") == "adjunto"
    assert sanear_nombre_adjunto("   ") == "adjunto"

    largo = sanear_nombre_adjunto("a" * 400 + ".pdf")
    assert len(largo) <= 120
    assert largo.endswith(".pdf")


def test_nombre_de_adjunto_en_el_zip() -> None:
    nombre = nombre_adjunto(EXPORTACION_ID, "radiografía 2026.jpg")
    assert nombre.startswith(f"adjuntos/{EXPORTACION_ID}_")
    assert nombre.endswith(".jpg")
    assert " " not in nombre


def test_manifiesto_informa_conteos_archivos_y_exclusiones() -> None:
    manifiesto = construir_manifiesto(
        exportacion_id=EXPORTACION_ID,
        alcance="paciente",
        generado_en=GENERADO_EN,
        filas_por_entidad={
            "pacientes": 1,
            "turnos": 4,
            "cobros": 2,
            "adjuntos": 0,
        },
        pdf_secciones=["pacientes", "turnos", "cobros"],
    )

    assert manifiesto["version"] == 1
    assert manifiesto["exportacion_id"] == str(EXPORTACION_ID)
    assert manifiesto["alcance"] == "paciente"
    assert manifiesto["generado_en"] == "2026-11-04T09:00:00-03:00"
    assert manifiesto["total_filas"] == 7

    entidades = {
        entidad["nombre"]: entidad for entidad in manifiesto["entidades"]
    }
    assert entidades["turnos"]["filas"] == 4
    assert entidades["turnos"]["archivo"] == "csv/turnos.csv"
    assert entidades["adjuntos"]["filas"] == 0
    assert manifiesto["pdf_secciones"] == [
        "pacientes",
        "turnos",
        "cobros",
    ]
    assert manifiesto["exclusiones"] == list(CAMPOS_EXCLUIDOS)


def test_exclusiones_nombran_los_secretos_que_nunca_salen() -> None:
    exclusiones = set(CAMPOS_EXCLUIDOS)
    assert "usuarios.hash_password" in exclusiones
    assert "turnos.token_publico" in exclusiones
    assert "comprobantes.claim_token" in exclusiones
    assert "cobros.link_pago" in exclusiones
    assert "mensajes_whatsapp.payload" in exclusiones
    assert "comprobantes.payload_envio" in exclusiones
    assert "comprobantes.respuesta_proveedor" in exclusiones
    assert "exportaciones.contenido" in exclusiones


def test_pdf_tiene_firma_pagina_totales_y_aviso_de_truncacion() -> None:
    filas = [
        {"id": f"t-{indice:04d}", "estado": "atendido"}
        for indice in range(MAX_FILAS_PDF + 100)
    ]
    pdf = generar_pdf_resumen(
        exportacion_id=EXPORTACION_ID,
        alcance="consultorio",
        generado_en=GENERADO_EN,
        consultorio="Consultorio Demo",
        secciones={"turnos": filas, "cobros": [{"id": "c-1"}]},
        totales={"turnos": len(filas), "cobros": 1},
    )

    assert pdf.startswith(b"%PDF-")
    assert _paginas(pdf) >= 1
    assert b"Consultorio Demo" in pdf
    assert b"primeras 500 filas" in pdf
    assert b"detalle completo" in pdf


def test_pdf_sin_truncacion_no_muestra_el_aviso() -> None:
    pdf = generar_pdf_resumen(
        exportacion_id=EXPORTACION_ID,
        alcance="paciente",
        generado_en=GENERADO_EN,
        consultorio="Consultorio Demo",
        secciones={"turnos": [{"id": "t-1"}, {"id": "t-2"}]},
        totales={"turnos": 2},
    )
    assert pdf.startswith(b"%PDF-")
    assert b"primeras 500 filas" not in pdf
    assert b"detalle completo" not in pdf
