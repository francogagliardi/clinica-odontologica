"""Model package: importing it registers every table on `Base.metadata`."""

from app.models.agenda import (
    Bloqueo,
    Profesional,
    ProfesionalSillon,
    Sillon,
    Turno,
)
from app.models.base import AuditMixin, Base
from app.models.caja import CajaDiaria, Cobro, MovimientoCaja
from app.models.clinica import (
    Adjunto,
    Consentimiento,
    Evolucion,
    HallazgoDental,
    HistoriaClinica,
    Odontograma,
)
from app.models.comercial import (
    ItemPresupuesto,
    ObraSocial,
    Prestacion,
    Presupuesto,
)
from app.models.comunicaciones import MensajeWhatsApp, Recordatorio
from app.models.fiscal import (
    Comprobante,
    ComprobanteEnvio,
    SecuenciaComprobante,
)
from app.models.liquidaciones import ItemLiquidacion, LiquidacionObraSocial
from app.models.lista_espera import EntradaListaEspera
from app.models.pacientes import Paciente
from app.models.reportes import Exportacion
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
    "CajaDiaria",
    "Cobro",
    "Comprobante",
    "ComprobanteEnvio",
    "Consentimiento",
    "Consultorio",
    "EntradaListaEspera",
    "Evolucion",
    "Exportacion",
    "HallazgoDental",
    "HistoriaClinica",
    "ItemLiquidacion",
    "ItemPresupuesto",
    "LiquidacionObraSocial",
    "MensajeWhatsApp",
    "MovimientoCaja",
    "ObraSocial",
    "Odontograma",
    "Paciente",
    "Prestacion",
    "Presupuesto",
    "Profesional",
    "ProfesionalSillon",
    "Recordatorio",
    "RegistroAuditoria",
    "Rol",
    "SecuenciaComprobante",
    "Sillon",
    "TokenUnSoloUso",
    "Turno",
    "Usuario",
    "UsuarioRol",
]
