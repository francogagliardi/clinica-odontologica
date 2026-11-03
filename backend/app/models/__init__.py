"""Model package: importing it registers every table on `Base.metadata`."""

from app.models.agenda import (
    Bloqueo,
    Profesional,
    ProfesionalSillon,
    Sillon,
)
from app.models.base import AuditMixin, Base
from app.models.comercial import Prestacion
from app.models.security import (
    Consultorio,
    RegistroAuditoria,
    Rol,
    Usuario,
    UsuarioRol,
)
from app.models.token import TokenUnSoloUso

__all__ = [
    "AuditMixin",
    "Base",
    "Bloqueo",
    "Consultorio",
    "Prestacion",
    "Profesional",
    "ProfesionalSillon",
    "RegistroAuditoria",
    "Rol",
    "Sillon",
    "TokenUnSoloUso",
    "Usuario",
    "UsuarioRol",
]
