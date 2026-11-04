"""Minimal WhatsApp templates with the tokenized management link (C-09/C-10)."""

from app.domain.agenda import ARGENTINA_OFFSET
from app.models.agenda import Profesional, Turno
from app.models.lista_espera import EntradaListaEspera
from app.models.pacientes import Paciente


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


def variables_oferta_hueco(
    *,
    entrada: EntradaListaEspera,
    paciente: Paciente,
    profesional: Profesional,
    oferta_url: str,
) -> dict[str, object]:
    """Variables of the freed-slot offer in Argentina local time (D9)."""
    inicio = entrada.oferta_inicio
    if inicio is None:  # defensive: only a retained entry is offered
        raise ValueError("La entrada de lista de espera no tiene horario")
    local = inicio.astimezone(ARGENTINA_OFFSET)
    return {
        "paciente": f"{paciente.nombre} {paciente.apellido}".strip(),
        "fecha": local.strftime("%d/%m/%Y"),
        "hora": local.strftime("%H:%M"),
        "matricula": profesional.matricula,
        "oferta_url": oferta_url,
        "vence_en": (
            entrada.oferta_expira_en.isoformat()
            if entrada.oferta_expira_en is not None
            else ""
        ),
        "mensaje": (
            f"Hola {paciente.nombre}, se liberó un turno el "
            f"{local.strftime('%d/%m/%Y')} a las {local.strftime('%H:%M')} "
            f"con el profesional {profesional.matricula}. "
            f"Reservalo acá: {oferta_url}"
        ),
    }
