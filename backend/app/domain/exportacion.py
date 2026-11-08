"""ZIP artifact contract for an exportation (C-15, design D4/D5/D6).

Pure definitions shared by the generator and the tests:

- the fixed file names (`exportacion.pdf`, `datos.json`, `manifiesto.json`);
- the canonical entity list and the mandatory exclusions (D6): credentials,
  public/single-use tokens, payment links and raw provider payloads never leave
  the system, while CAE/QR and amounts do;
- attachment-name sanitization so a stored name cannot escape `adjuntos/`;
- the manifest builder, which makes completeness verifiable (row counts) and
  states exactly what was not exported.

The PDF summary is capped at 500 rows per section (D4); the structured JSON and
CSV files are complete.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from app.domain.reportes import formatear_local

NOMBRE_PDF = "exportacion.pdf"
NOMBRE_DATOS = "datos.json"
NOMBRE_MANIFIESTO = "manifiesto.json"
MAX_FILAS_PDF = 500
VERSION_ARTEFACTO = 1
_MAX_NOMBRE = 120

# Canonical order of the ERD entities present in the artifact (D6). `usuarios`
# is exported as a minimal directory only, never with credentials.
ENTIDADES_EXPORTABLES: tuple[str, ...] = (
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
)

# D6/RN-SE-03: every field or table deliberately left out of the ZIP. The
# manifest repeats this list so the user knows what was not exported and why.
CAMPOS_EXCLUIDOS: tuple[str, ...] = (
    "usuarios.hash_password",
    "turnos.token_publico",
    "tokens_un_solo_uso",
    "comprobantes.claim_token",
    "exportaciones.contenido",
    "cobros.link_pago",
    "cobros.proveedor_pago_id",
    "cobros.proveedor_preferencia_id",
    "comprobantes_envios.proveedor_mensaje_id",
    "mensajes_whatsapp.proveedor_mensaje_id",
    "mensajes_whatsapp.payload",
    "comprobantes.payload_envio",
    "comprobantes.respuesta_proveedor",
    "adjuntos.contenido",
    "configuracion.secretos",
)

_NO_PERMITIDO = re.compile(r"[^A-Za-z0-9._-]+")
_REPETIDOS = re.compile(r"_+")


@dataclass(frozen=True)
class AdjuntoExportado:
    """One binary entry of the ZIP, already sanitized and namespaced."""

    ruta: str
    contenido: bytes


def sanear_nombre_adjunto(nombre: str) -> str:
    """Turn an untrusted stored name into one safe ZIP entry component.

    The basename is taken first (so `../` never survives), every character
    outside the conservative set becomes `_`, repeated separators collapse and
    the extension is preserved when the name must be truncated.
    """
    base = str(nombre or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    limpio = _NO_PERMITIDO.sub("_", base)
    limpio = _REPETIDOS.sub("_", limpio).strip("._")
    if not limpio or limpio in {".", ".."}:
        return "adjunto"
    if len(limpio) > _MAX_NOMBRE:
        raiz, punto, extension = limpio.rpartition(".")
        if punto and 0 < len(extension) <= 10:
            recorte = _MAX_NOMBRE - len(extension) - 1
            limpio = f"{limpio[:recorte].rstrip('._')}.{extension}"
        else:
            limpio = limpio[:_MAX_NOMBRE].rstrip("._")
    return limpio or "adjunto"


def nombre_csv(entidad: str) -> str:
    """One CSV per entity, always under `csv/`."""
    return f"csv/{entidad}.csv"


def nombre_adjunto(adjunto_id: uuid.UUID | str, nombre: str) -> str:
    """`adjuntos/<id>_<sanitized-name>`: unique and traversal-proof."""
    return f"adjuntos/{adjunto_id}_{sanear_nombre_adjunto(nombre)}"


def construir_manifiesto(
    *,
    exportacion_id: uuid.UUID | str,
    alcance: str,
    generado_en: datetime,
    filas_por_entidad: Mapping[str, int],
    pdf_secciones: Sequence[str],
) -> dict[str, object]:
    """Build `manifiesto.json` with counts, file names and exclusions.

    Entities follow the canonical order; an entity present in the artifact but
    not in the canonical list is appended sorted, so the output is stable.
    """
    conocidas = [
        entidad
        for entidad in ENTIDADES_EXPORTABLES
        if entidad in filas_por_entidad
    ]
    desconocidas = sorted(set(filas_por_entidad) - set(conocidas))
    ordenadas = [*conocidas, *desconocidas]
    filas = int(sum(int(filas_por_entidad[nombre]) for nombre in ordenadas))
    entidades = [
        {
            "nombre": nombre,
            "filas": int(filas_por_entidad[nombre]),
            "archivo": nombre_csv(nombre),
        }
        for nombre in ordenadas
    ]
    return {
        "version": VERSION_ARTEFACTO,
        "exportacion_id": str(exportacion_id),
        "alcance": alcance,
        "generado_en": formatear_local(generado_en),
        "entidades": entidades,
        "total_filas": filas,
        "pdf_secciones": list(pdf_secciones),
        "exclusiones": list(CAMPOS_EXCLUIDOS),
    }
