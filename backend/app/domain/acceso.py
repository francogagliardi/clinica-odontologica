"""Pure access-management rules (C-16, design D3/D4/D5/D12).

No I/O and no framework imports: the API layer and the repositories consume
these helpers, so the five-role catalogue, the email canonical form, the audit
action names and the viewer pagination have a single source of truth.
"""

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

# Fixed catalogue of `03_actores_y_roles.md`: no role can be created, renamed or
# deleted through the API (design D3).
ROLES_CATALOGO: tuple[str, ...] = (
    "administrador",
    "odontologo",
    "recepcionista",
    "asistente",
    "auditor",
)

# Stable audit action names read by the viewer (design D12).
ACCION_USUARIO_CREAR = "usuario.crear"
ACCION_USUARIO_EDITAR = "usuario.editar"
ACCION_USUARIO_PASSWORD = "usuario.password"
ACCION_USUARIO_ROLES = "usuario.roles"
ACCION_USUARIO_ACTIVAR = "usuario.activar"
ACCION_USUARIO_DESACTIVAR = "usuario.desactivar"

ACCIONES_AUDITORIA: frozenset[str] = frozenset(
    {
        ACCION_USUARIO_CREAR,
        ACCION_USUARIO_EDITAR,
        ACCION_USUARIO_PASSWORD,
        ACCION_USUARIO_ROLES,
        ACCION_USUARIO_ACTIVAR,
        ACCION_USUARIO_DESACTIVAR,
    }
)

# Audit viewer bounds (design D5). They are also the query defaults/limits.
LIMITE_DEFAULT = 100
LIMITE_MAXIMO = 500

# Constant key of the global advisory lock that serializes access mutations
# (design D2): a low-volume, deterministic value owned by this module.
CLAVE_BLOQUEO_ACCESO = 160016

_EMAIL_MAX_LENGTH = 255
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalizar_email(email: str) -> str:
    """Canonical form: trimmed and lower-cased (login is case-insensitive)."""
    return email.strip().lower()


def es_email_valido(email: str) -> bool:
    """Structural check: one `@`, a dot in the domain and no whitespace."""
    normalizado = normalizar_email(email)
    return (
        len(normalizado) <= _EMAIL_MAX_LENGTH
        and _EMAIL_RE.fullmatch(normalizado) is not None
    )


def validar_roles(roles: Sequence[str]) -> tuple[str, ...]:
    """Validate the fixed catalogue and deduplicate preserving input order.

    An empty list, an unknown name or a different casing raises `ValueError`,
    which the API boundary maps to HTTP 422 without touching the database.
    """
    if not roles:
        raise ValueError("La lista de roles no puede estar vacía")
    vistos: list[str] = []
    for rol in roles:
        if rol not in ROLES_CATALOGO:
            raise ValueError(f"Rol desconocido: {rol}")
        if rol not in vistos:
            vistos.append(rol)
    return tuple(vistos)


@dataclass(frozen=True)
class Paginacion:
    """Resolved viewer page: the API never recomputes these bounds."""

    total: int
    limite: int
    offset: int

    @property
    def total_paginas(self) -> int:
        if self.total <= 0:
            return 0
        return math.ceil(self.total / self.limite)

    @property
    def pagina_actual(self) -> int:
        return self.offset // self.limite + 1

    @property
    def hay_siguiente(self) -> bool:
        return self.offset + self.limite < self.total

    @property
    def hay_anterior(self) -> bool:
        return self.offset > 0


def validar_paginacion(limite: int, offset: int) -> None:
    """Reject out-of-range viewer bounds before querying (422 at the edge)."""
    if limite < 1 or limite > LIMITE_MAXIMO:
        raise ValueError(
            f"limite debe estar entre 1 y {LIMITE_MAXIMO}"
        )
    if offset < 0:
        raise ValueError("offset debe ser mayor o igual a 0")


def calcular_paginacion(
    total: int,
    limite: int = LIMITE_DEFAULT,
    offset: int = 0,
) -> Paginacion:
    """Compute the viewer page from the total read before paginating."""
    validar_paginacion(limite, offset)
    return Paginacion(total=max(total, 0), limite=limite, offset=offset)
