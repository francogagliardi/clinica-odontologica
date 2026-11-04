"""Versioned informed-consent catalogue and canonical digests (C-11, RN-CL-03).

The text lives in code so the version recorded in the database always resolves
to the exact wording the patient accepted. No graphic signature is stored: the
hashes are integrity references (design D10), not a legal digital signature.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

TIPOS_VALIDOS = frozenset({"procedimiento_invasivo"})

TEXTOS: dict[str, str] = {
    "v1-2026-11": (
        "Consentimiento informado para procedimientos odontológicos invasivos.\n"
        "El/la paciente declara haber recibido información comprensible sobre "
        "el diagnóstico, el procedimiento propuesto, sus alternativas, los "
        "riesgos y beneficios esperados, y haber podido formular preguntas. "
        "Autoriza la realización del procedimiento por el profesional "
        "interviniente y registra su conformidad en la historia clínica."
    )
}

VERSION_ACTUAL = "v1-2026-11"


def tipo_valido(tipo: str) -> bool:
    """Only the catalogue types can be recorded."""
    return tipo in TIPOS_VALIDOS


def version_conocida(version: str) -> bool:
    """True when the requested text version exists in this build."""
    return version in TEXTOS


def texto_canonico(version: str) -> str:
    """Resolve the exact wording of a version; unknown versions are an error."""
    try:
        return TEXTOS[version]
    except KeyError as error:
        raise ValueError(
            f"Versión de consentimiento desconocida: {version}"
        ) from error


def calcular_hashes(
    *, version: str, paciente_id: uuid.UUID, fecha: datetime
) -> tuple[str, str]:
    """Return `(texto_hash, firma_ref)` for the canonical consent.

    `texto_hash` is the SHA-256 of the canonical text; `firma_ref` is the
    SHA-256 of text hash + patient + ISO date, so the same act has a stable,
    verifiable reference without storing a signature image.
    """
    texto = texto_canonico(version)
    texto_hash = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    firma_ref = "sha256:" + hashlib.sha256(
        f"{texto_hash}{paciente_id}{fecha.isoformat()}".encode("utf-8")
    ).hexdigest()
    return texto_hash, firma_ref
