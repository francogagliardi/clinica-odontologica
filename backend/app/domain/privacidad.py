"""Versioned privacy policy published as public content (C-16, design D7).

The text lives in the repository, is immutable per version and is hashed with
SHA-256 so a client can prove which version it read. This module deliberately
contains no acceptance logic: publishing the policy does not change the public
booking contract (no checkbox, no new reservation fields, no acceptance event).

The legal scope is documented as human validation: the text names Ley 25.326
and Ley 26.529 only to state that it is not a declaration of compliance.
"""

import hashlib
from dataclasses import dataclass
from datetime import date

VERSION_ACTUAL = "v1-2026-11"
VIGENTE_DESDE = date(2026, 11, 1)

_TEXTO_BASE = """Política de privacidad — versión {version} (vigente desde {vigencia}).

Esta política describe qué datos trata la clínica para gestionar turnos,
atenciones, presupuestos y cobros, y cómo se protegen. Los datos de salud se
conservan en la base clínica y solo se comparten con el paciente y con el
personal autorizado por la clínica.

La reserva pública no exige aceptar esta política: se muestra como información.
El consentimiento informado de las prácticas invasivas se registra por separado
en la historia clínica.

El alcance legal frente a la Ley 25.326 y la Ley 26.529 debe validarse con
asesoramiento humano. Este texto es un borrador técnico y no constituye una
declaración de cumplimiento normativo ni una garantía legal.
"""


@dataclass(frozen=True)
class PoliticaPrivacidad:
    """One immutable published version."""

    version: str
    vigente_desde: date
    texto: str


def _construir(version: str, vigente_desde: date) -> PoliticaPrivacidad:
    return PoliticaPrivacidad(
        version=version,
        vigente_desde=vigente_desde,
        texto=_TEXTO_BASE.format(
            version=version, vigencia=vigente_desde.isoformat()
        ),
    )


POLITICAS: dict[str, PoliticaPrivacidad] = {
    VERSION_ACTUAL: _construir(VERSION_ACTUAL, VIGENTE_DESDE),
}


def politica_actual() -> PoliticaPrivacidad:
    """The version published at `GET /privacidad`."""
    return POLITICAS[VERSION_ACTUAL]


def politica_por_version(version: str) -> PoliticaPrivacidad | None:
    """Exact version lookup; an unknown version is `None` (HTTP 404)."""
    return POLITICAS.get(version)


def hash_politica(texto: str) -> str:
    """SHA-256 of the canonical UTF-8 text (stable across processes)."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
