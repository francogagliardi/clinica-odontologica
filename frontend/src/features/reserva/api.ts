/** Public booking API client (C-07). No business rules live here (R-07). */

import { fetchJson, postJson } from "../../shared/api/client";

export interface ProfesionalPublico {
  id: string;
  matricula: string;
  especialidades: string[];
}

export interface PrestacionPublica {
  id: string;
  codigo: string;
  nombre: string;
  duracion_min: number;
  precio_base: string;
  especialidad: string | null;
  requiere_sena: boolean;
  monto_sena: string | null;
}

export interface CatalogoPublico {
  slug: string;
  nombre: string;
  profesionales: ProfesionalPublico[];
  prestaciones: PrestacionPublica[];
  plazo_cancelacion_horas: number;
  politica_cancelacion: string;
  politica_sena: string;
  moneda: string;
}

export interface SlotPublico {
  inicio: string;
  fin: string;
}

export interface SenaPublica {
  requiere: boolean;
  monto: string | null;
  estado: string;
}

export interface ReservaResponse {
  turno_id: string;
  inicio: string;
  fin: string;
  estado: string;
  profesional: ProfesionalPublico;
  prestacion: PrestacionPublica | null;
  sena: SenaPublica;
  gestion_url: string;
  whatsapp_confirmacion: string;
  plazo_cancelacion_horas: number;
  politica_sena: string;
}

export interface GestionTurnoResponse {
  turno_id: string;
  inicio: string;
  fin: string;
  estado: string;
  profesional: ProfesionalPublico;
  prestacion: PrestacionPublica | null;
  sena: SenaPublica;
  puede_confirmar: boolean;
  puede_cancelar: boolean;
  plazo_cancelacion_horas: number;
  politica_sena: string;
}

export interface AccionResponse {
  estado: string;
  sena_perdida: boolean;
}

export interface ReservaPayload {
  nombre: string;
  apellido: string;
  dni: string;
  telefono: string;
  email?: string;
  profesional_id: string;
  prestacion_id: string | null;
  inicio: string;
}

export function fetchCatalogo(): Promise<CatalogoPublico> {
  return fetchJson("/reservar/demo") as Promise<CatalogoPublico>;
}

export function fetchDisponibilidad(
  profesionalId: string,
  prestacionId: string | null,
  fecha: string,
): Promise<SlotPublico[]> {
  const params = new URLSearchParams({
    fecha,
    profesional_id: profesionalId,
  });
  if (prestacionId !== null) {
    params.set("prestacion_id", prestacionId);
  }
  return fetchJson(
    `/reservar/demo/disponibilidad?${params.toString()}`,
  ) as Promise<SlotPublico[]>;
}

export function crearReserva(payload: ReservaPayload): Promise<ReservaResponse> {
  return postJson("/reservar/demo/turnos", payload) as Promise<ReservaResponse>;
}

export function fetchGestion(token: string): Promise<GestionTurnoResponse> {
  return fetchJson(
    `/reservar/gestion/${encodeURIComponent(token)}`,
  ) as Promise<GestionTurnoResponse>;
}

export function confirmarTurno(token: string): Promise<AccionResponse> {
  return postJson(
    `/reservar/gestion/${encodeURIComponent(token)}/confirmar`,
    {},
  ) as Promise<AccionResponse>;
}

export function cancelarTurno(token: string): Promise<AccionResponse> {
  return postJson(
    `/reservar/gestion/${encodeURIComponent(token)}/cancelar`,
    {},
  ) as Promise<AccionResponse>;
}
