"""Model package: importing it registers every table on `Base.metadata`."""

from app.models.base import AuditMixin, Base
from app.models.security import (
    Consultorio,
    RegistroAuditoria,
    Rol,
    Usuario,
    UsuarioRol,
)

__all__ = [
    "AuditMixin",
    "Base",
    "Consultorio",
    "RegistroAuditoria",
    "Rol",
    "Usuario",
    "UsuarioRol",
]
