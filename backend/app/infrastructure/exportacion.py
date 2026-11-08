"""PDF summary of an exportation with `fpdf2` (C-15, design D4).

`fpdf2` is pure Python and works on `python:3.12-slim` without system fonts,
which is why it wins over WeasyPrint/ReportLab for a containerised demo. The
PDF is a **readable summary**: header, totals and up to 500 rows per section;
the complete data lives in `datos.json` and the per-entity CSV files.

Core fonts are Latin-1, so every string goes through `_latin1`: Spanish accents
render and an unexpected character is replaced instead of failing the job.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
import zipfile
from collections.abc import Mapping, Sequence
from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos

from app.domain.exportacion import (
    MAX_FILAS_PDF,
    NOMBRE_DATOS,
    NOMBRE_MANIFIESTO,
    NOMBRE_PDF,
    AdjuntoExportado,
    construir_manifiesto,
    nombre_csv,
)
from app.domain.reportes import formatear_local

_ANCHO_TOTAL = 0


def _latin1(valor: object, limite: int | None = None) -> str:
    texto = str(valor).replace("\r", " ").replace("\n", " ")
    if limite is not None and len(texto) > limite:
        texto = f"{texto[:limite - 1]}…"
    return texto.encode("latin-1", "replace").decode("latin-1")


def _linea(fila: Mapping[str, object]) -> str:
    return " | ".join(
        f"{clave}={_latin1(valor, 60)}" for clave, valor in fila.items()
    )


def generar_pdf_resumen(
    *,
    exportacion_id: uuid.UUID | str,
    alcance: str,
    generado_en: datetime,
    consultorio: str,
    secciones: Mapping[str, Sequence[Mapping[str, object]]],
    totales: Mapping[str, object] | None = None,
) -> bytes:
    """Render the PDF summary; deterministic and never empty (one page min).

    Sections are capped at `MAX_FILAS_PDF` rows with an explicit notice; the
    structured files remain complete, so the summary never pretends to be the
    only source of data.
    """
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_compression(False)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(
        _ANCHO_TOTAL,
        10,
        _latin1("Exportación de datos"),
        new_x=XPos.LMARGIN,
    )
    pdf.ln(6)

    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        _ANCHO_TOTAL,
        6,
        _latin1(f"Consultorio: {consultorio}"),
        new_x=XPos.LMARGIN,
    )
    pdf.multi_cell(
        _ANCHO_TOTAL,
        6,
        _latin1(
            f"Alcance: {alcance} | Generado: {formatear_local(generado_en)}"
        ),
        new_x=XPos.LMARGIN,
    )
    pdf.multi_cell(
        _ANCHO_TOTAL,
        6,
        _latin1(f"Exportación: {exportacion_id}"),
        new_x=XPos.LMARGIN,
    )
    pdf.ln(3)

    for nombre, filas in secciones.items():
        total = (
            totales.get(nombre) if totales is not None else None
        )
        if total is None:
            total = len(filas)

        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(
            _ANCHO_TOTAL,
            7,
            _latin1(f"Sección: {nombre} ({int(total)} filas)"),
            new_x=XPos.LMARGIN,
        )
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(
            _ANCHO_TOTAL,
            5,
            _latin1(f"Total: {total}"),
            new_x=XPos.LMARGIN,
        )

        visibles = list(filas)[:MAX_FILAS_PDF]
        for fila in visibles:
            pdf.multi_cell(
                _ANCHO_TOTAL,
                4,
                _latin1(_linea(fila), 200),
                new_x=XPos.LMARGIN,
            )

        if int(total) > MAX_FILAS_PDF or len(filas) > MAX_FILAS_PDF:
            pdf.set_font("Helvetica", "I", 8)
            pdf.multi_cell(
                _ANCHO_TOTAL,
                5,
                _latin1(
                    f"Se muestran las primeras {MAX_FILAS_PDF} filas de "
                    f"{int(total)}; el detalle completo esta en "
                    "datos.json y los CSV."
                ),
                new_x=XPos.LMARGIN,
            )
        pdf.ln(3)

    return bytes(pdf.output())


def _csv_value(valor: object) -> str:
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False, sort_keys=True)
    return str(valor)


def _csv_entidad(
    columnas: Sequence[str],
    filas: Sequence[Mapping[str, object]],
) -> str:
    salida = io.StringIO(newline="")
    escritor = csv.DictWriter(
        salida,
        fieldnames=list(columnas),
        extrasaction="ignore",
        lineterminator="\n",
    )
    escritor.writeheader()
    for fila in filas:
        escritor.writerow(
            {columna: _csv_value(fila.get(columna)) for columna in columnas}
        )
    return salida.getvalue()


def construir_zip(
    *,
    exportacion_id: uuid.UUID | str,
    alcance: str,
    generado_en: datetime,
    consultorio: Mapping[str, object],
    entidades: Mapping[str, Sequence[Mapping[str, object]]],
    columnas: Mapping[str, Sequence[str]],
    adjuntos: Sequence[AdjuntoExportado],
) -> bytes:
    """Build the complete ZIP: PDF, JSON, manifest, CSVs and binary attachments."""
    pdf = generar_pdf_resumen(
        exportacion_id=exportacion_id,
        alcance=alcance,
        generado_en=generado_en,
        consultorio=str(consultorio.get("nombre", "")),
        secciones=entidades,
        totales={
            entidad: len(filas) for entidad, filas in entidades.items()
        },
    )
    manifiesto = construir_manifiesto(
        exportacion_id=exportacion_id,
        alcance=alcance,
        generado_en=generado_en,
        filas_por_entidad={
            entidad: len(filas) for entidad, filas in entidades.items()
        },
        pdf_secciones=list(entidades),
    )
    datos: dict[str, object] = {
        "version": 1,
        "exportacion_id": str(exportacion_id),
        "alcance": alcance,
        "generado_en": formatear_local(generado_en),
        "consultorio": dict(consultorio),
    }
    datos.update({entidad: list(filas) for entidad, filas in entidades.items()})

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archivo:
        archivo.writestr(NOMBRE_PDF, pdf)
        archivo.writestr(
            NOMBRE_DATOS,
            json.dumps(datos, ensure_ascii=False, indent=2),
        )
        archivo.writestr(
            NOMBRE_MANIFIESTO,
            json.dumps(manifiesto, ensure_ascii=False, indent=2),
        )
        for entidad, filas in entidades.items():
            columnas_entidad = list(
                columnas.get(
                    entidad,
                    sorted(
                        {
                            clave
                            for fila in filas
                            for clave in fila.keys()
                        }
                    ),
                )
            )
            archivo.writestr(
                nombre_csv(entidad),
                _csv_entidad(columnas_entidad, filas),
            )
        for adjunto in adjuntos:
            archivo.writestr(adjunto.ruta, adjunto.contenido)
    return buffer.getvalue()
