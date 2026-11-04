"""Model package: importing it registers every table on `Base.metadata`."""

from app.models.agenda import (
    Bloqueo,
    Profesional,
    ProfesionalSillon,
    Sillon,
    Turno,
)
from app.models.base import AuditMixin, Base
from app.models.clinica import (
    Adjunto,
    Consentimiento,
    Evolucion,
    HallazgoDental,
    HistoriaClinica,
    Odontograma,
)
from app.models.comercial import ObraSocial, Prestacion
from app.models.comunicaciones import MensajeWhatsApp, Recordatorio
from app.models.lista_espera import EntradaListaEspera
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
    "Adjunto",
    "AuditMixin",
    "Base",
    "Bloqueo",
    "Consentimiento",
    "Consultorio",
    "EntradaListaEspera",
    "Evolucion",
    "HallazgoDental",
    "HistoriaClinica",
    "MensajeWhatsApp",
    "ObraSocial",
    "Odontograma",
    "Paciente",
    "Prestacion",
    "Profesional",
    "ProfesionalSillon",
    "Recordatorio",
    "RegistroAuditoria",
    "Rol",
    "Sillon",
    "TokenUnSoloUso",
    "Turno",
    "Usuario",
    "UsuarioRol",
]
