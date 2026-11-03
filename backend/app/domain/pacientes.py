"""Pure patient-identity normalization (C-05, design D3).

No I/O here: C-07 will reuse these functions when a public booking collects a
phone number, and unit tests pin the accepted formats.
"""

import re

_LIMPIAR_DNI = re.compile(r"[\s.\-]")
_NO_DIGITO = re.compile(r"\D")


def normalizar_dni(raw: str) -> str:
    """Return the DNI as 7-8 digits, or raise `ValueError`."""
    limpio = _LIMPIAR_DNI.sub("", raw or "")
    if not limpio.isdigit() or len(limpio) not in (7, 8):
        raise ValueError("El DNI debe tener 7 u 8 dígitos")
    return limpio


def normalizar_telefono(raw: str) -> str:
    """Return a canonical Argentine mobile number (`+549...`) or raise.

    Accepts 10 national digits (area + number) or 13 digits already carrying
    the `549` mobile prefix. Landlines and other lengths are rejected because
    WhatsApp is the clinic channel (design D3).
    """
    digitos = _NO_DIGITO.sub("", raw or "")
    if len(digitos) == 10:
        return f"+549{digitos}"
    if len(digitos) == 13 and digitos.startswith("549"):
        return f"+{digitos}"
    raise ValueError(
        "El teléfono debe ser un celular argentino: 10 dígitos o +549..."
    )
