/** Audit viewer API: read-only, authenticated and paginated (C-16). */

import { fetchJson } from "../../shared/api/client";
import { authHeaders } from "../auth/session";

export interface AuditoriaFila {
  id: string;
  usuario_id: string | null;
  usuario_email: string | null;
  accion: string;
  entidad: string;
  entidad_id: string;
  ip: string | null;
  dispositivo: string | null;
  timestamp: string;
}

export interface AuditoriaResponse {
  total: number;
  limite: number;
  offset: number;
  filas: AuditoriaFila[];
}

export interface FiltrosAuditoria {
  usuarioId?: string;
  entidad?: string;
  accion?: string;
  desde?: string;
  hasta?: string;
  limite: number;
  offset: number;
}

export function fetchAuditoria(
  filtros: FiltrosAuditoria,
): Promise<AuditoriaResponse> {
  const params = new URLSearchParams();
  if (filtros.usuarioId !== undefined && filtros.usuarioId !== "") {
    params.set("usuario_id", filtros.usuarioId);
  }
  if (filtros.entidad !== undefined && filtros.entidad !== "") {
    params.set("entidad", filtros.entidad);
  }
  if (filtros.accion !== undefined && filtros.accion !== "") {
    params.set("accion", filtros.accion);
  }
  if (filtros.desde !== undefined && filtros.desde !== "") {
    params.set("desde", filtros.desde);
  }
  if (filtros.hasta !== undefined && filtros.hasta !== "") {
    params.set("hasta", filtros.hasta);
  }
  params.set("limite", String(filtros.limite));
  params.set("offset", String(filtros.offset));
  return fetchJson(
    `/auditoria?${params.toString()}`,
    authHeaders(),
  ) as Promise<AuditoriaResponse>;
}
