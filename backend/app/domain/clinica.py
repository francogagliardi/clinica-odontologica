"""Pure clinical domain: FDI notation, faces, states and CIE-10 (C-11).

No I/O here: the same predicates are mirrored by CHECK constraints in
migration 0010, so the HTTP edge and PostgreSQL agree on what is a valid
tooth, face, clinical state or diagnosis code (RN-CL-01, design D6).
"""

from __future__ import annotations

import re

# FDI: permanent 11-18 / 21-28 / 31-38 / 41-48 and temporary 51-55 / 61-65 /
# 71-75 / 81-85. The two-range formula is what rejects 19, 20, 29, 49, 56, 86.
PIEZAS_PERMANENTES = frozenset(
    cuadrante * 10 + diente
    for cuadrante in (1, 2, 3, 4)
    for diente in range(1, 9)
)
PIEZAS_TEMPORARIAS = frozenset(
    cuadrante * 10 + diente
    for cuadrante in (5, 6, 7, 8)
    for diente in range(1, 6)
)
PIEZAS_VALIDAS = PIEZAS_PERMANENTES | PIEZAS_TEMPORARIAS

CARAS_VALIDAS = frozenset(
    {
        "mesial",
        "distal",
        "vestibular",
        "lingual",
        "oclusal",
        "incisal",
        "completa",
    }
)

ESTADOS_VALIDOS = frozenset(
    {
        "sano",
        "caries",
        "obturacion",
        "endodoncia",
        "corona",
        "implante",
        "ausente",
        "extraccion_indicada",
        "fractura",
        "sellante",
        "protesis",
    }
)

_CIE10_PATTERN = re.compile(r"^[A-Z][0-9]{2}(\.[0-9]{1,2})?$")

# Attachments (design D7): self-contained bytes, allow-list and magic bytes.
MAX_ADJUNTO_BYTES = 5 * 1024 * 1024
MAX_NOMBRE_ADJUNTO = 255
MIMES_PERMITIDOS = frozenset(
    {"image/jpeg", "image/png", "image/webp", "application/pdf"}
)

# Defence in depth: even a forged MIME cannot smuggle an executable or an
# active document through a filename the browser might later trust.
EXTENSIONES_PELIGROSAS = frozenset(
    {
        ".exe",
        ".dll",
        ".com",
        ".scr",
        ".msi",
        ".bat",
        ".cmd",
        ".ps1",
        ".sh",
        ".js",
        ".jar",
        ".html",
        ".htm",
        ".svg",
        ".php",
        ".zip",
    }
)

_FIRMAS: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "application/pdf": (b"%PDF",),
}



def pieza_fdi_valida(pieza: int) -> bool:
    """True only for a real FDI tooth (mirrors the SQL two-range formula)."""
    if not isinstance(pieza, int) or isinstance(pieza, bool):
        return False
    return pieza in PIEZAS_VALIDAS


def cara_valida(cara: str) -> bool:
    """Faces of the tooth; `completa` represents whole-tooth states."""
    return cara in CARAS_VALIDAS


def estado_valido(estado: str) -> bool:
    """Clinical state catalogue allowed by RN-CL-01."""
    return estado in ESTADOS_VALIDOS


def cie10_valido(cie10: str | None) -> bool:
    """Optional CIE-10 code: absent is valid, present must match the format."""
    if cie10 is None:
        return True
    return _CIE10_PATTERN.fullmatch(cie10) is not None


def sanear_nombre(nombre: str) -> str:
    """Reduce a client filename to a safe basename (design D7).

    Only metadata is stored, but the name is served in `Content-Disposition`,
    so separators and relative-path markers are removed instead of escaped.
    """
    if not nombre:
        return "adjunto"
    limpio = nombre.replace("\\", "/").split("/")[-1]
    limpio = limpio.replace("\x00", "").strip()
    # Control characters and quotes would be dangerous in Content-Disposition.
    limpio = "".join(
        caracter
        for caracter in limpio
        if caracter.isprintable() and caracter != '"'
    ).strip()
    # Leading dots would leave hidden/relative markers such as `..` or `.env`.
    limpio = limpio.lstrip(".").strip()
    if not limpio or limpio in {".", ".."}:
        return "adjunto"
    return limpio[:MAX_NOMBRE_ADJUNTO]


def mime_permitido(mime: str) -> bool:
    """Allow-list check, case-insensitive and tolerant of parameters."""
    return mime.split(";")[0].strip().lower() in MIMES_PERMITIDOS


def extension_peligrosa(nombre: str) -> bool:
    """True for executable/active extensions, regardless of the declared MIME."""
    return any(
        nombre.strip().lower().endswith(extension)
        for extension in EXTENSIONES_PELIGROSAS
    )


def firma_coincide_con_mime(mime: str, contenido: bytes) -> bool:
    """Verify the real file signature matches the declared MIME (D7).

    Magic bytes are not an antivirus, but they stop mislabelled executables,
    HTML or ZIPs from being stored and later served as a trusted image.
    """
    normalizado = mime.split(";")[0].strip().lower()
    if not mime_permitido(normalizado) or not contenido:
        return False
    if normalizado == "image/webp":
        return (
            len(contenido) >= 12
            and contenido[:4] == b"RIFF"
            and contenido[8:12] == b"WEBP"
        )
    return any(
        contenido.startswith(firma)
        for firma in _FIRMAS.get(normalizado, ())
    )
