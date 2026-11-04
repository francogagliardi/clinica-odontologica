"""Model package: importing it registers every table on `Base.metadata`."""

from app.models.agenda import (
    Bloqueo,
    Profesional,
    ProfesionalSillon,
    Sillon,
    Turno,
)
from app.models.base import AuditMixin, Base
from app.models.comercial import ObraSocial, Prestacion
from app.models.pacientes import Paciente
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
    "ObraSocial",
    "Paciente",
    "Prestacion",
    "Profesional",
    "ProfesionalSillon",
    "RegistroAuditoria",
    "Rol",
    "Sillon",
    "TokenUnSoloUso",
    "Turno",
    "Usuario",
    "UsuarioRol",
]
