"""Minimal WhatsApp templates with the tokenized management link (C-09)."""

from app.domain.agenda import ARGENTINA_OFFSET
from app.models.agenda import Turno
from app.models.pacientes import Paciente
from app.models.agenda import Profesional


def variables_recordatorio(
    *,
    turno: Turno,
    paciente: Paciente,
    profesional: Profesional,
    gestion_url: str,
) -> dict[str, object]:
    local = turno.inicio.astimezone(ARGENTINA_OFFSET)
    return {
        "paciente": f"{paciente.nombre} {paciente.apellido}".strip(),
        "fecha": local.strftime("%d/%m/%Y"),
        "hora": local.strftime("%H:%M"),
        "matricula": profesional.matricula,
        "gestion_url": gestion_url,
        "mensaje": (
            f"Hola {paciente.nombre}, te recordamos tu turno del "
            f"{local.strftime('%d/%m/%Y')} a las {local.strftime('%H:%M')} "
            f"con el profesional {profesional.matricula}. "
            f"Gestioná tu turno acá: {gestion_url}"
        ),
    }
