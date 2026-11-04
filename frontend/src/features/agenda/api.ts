/** Agenda API client: authenticated reads and preview of reprogramming. */

import { fetchJson, patchJson } from "../../shared/api/client";
import { authHeaders } from "../auth/session";

export interface Turno {
  id: string;
  paciente_id: string;
  profesional_id: string;
  sillon_id: string;
  prestacion_id: string | null;
  inicio: string;
  fin: string;
  estado: string;
  origen: string;
  es_sobreturno: boolean;
  color_sobreturno: string | null;
}

export interface Bloqueo {
  id: string;
  profesional_id: string | null;
  sillon_id: string | null;
  desde: string;
  hasta: string;
  motivo: string;
}

export interface Profesional {
  id: string;
  usuario_id: string | null;
  matricula: string;
  especialidades: string[];
}

export interface Sillon {
  id: string;
  nombre: string;
}

export interface Prestacion {
  id: string;
  codigo: string;
  nombre: string;
  duracion_min: number;
}

function query(params: Record<string, string | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== "") {
      search.set(key, value);
    }
  }
  return search.toString();
}

export function fetchProfesionales(): Promise<Profesional[]> {
  return fetchJson("/profesionales", authHeaders()) as Promise<Profesional[]>;
}

export function fetchSillones(): Promise<Sillon[]> {
  return fetchJson("/sillones", authHeaders()) as Promise<Sillon[]>;
}

export function fetchPrestaciones(): Promise<Prestacion[]> {
  return fetchJson("/prestaciones", authHeaders()) as Promise<Prestacion[]>;
}

export function fetchTurnos(
  desde: string,
  hasta: string,
  profesionalId: string | null,
  sillonId: string | null,
): Promise<Turno[]> {
  const search = query({
    desde,
    hasta,
    profesional_id: profesionalId,
    sillon_id: sillonId,
  });
  return fetchJson(`/turnos?${search}`, authHeaders()) as Promise<Turno[]>;
}

export function fetchBloqueos(
  desde: string,
  hasta: string,
): Promise<Bloqueo[]> {
  const search = query({
    desde: `${desde}T00:00:00-03:00`,
    hasta: `${hasta}T23:59:59-03:00`,
  });
  return fetchJson(`/bloqueos?${search}`, authHeaders()) as Promise<Bloqueo[]>;
}

export function reprogramarTurno(
  id: string,
  inicio: string,
): Promise<Turno> {
  return patchJson(
    `/turnos/${id}/reprogramar`,
    { inicio },
    authHeaders(),
  ) as Promise<Turno>;
}
