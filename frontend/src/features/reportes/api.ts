/** Reports and exportations API: authenticated reads, jobs and ZIP download. */

import { ApiError, fetchJson, getApiBaseUrl, postJson } from "../../shared/api/client";
import { authHeaders } from "../auth/session";

export type Fila = Record<string, unknown>;

export interface ReporteAgenda {
  total_turnos: number;
  por_estado: Record<string, number>;
  cancelaciones: number;
  minutos_disponibles: number;
  minutos_ocupados: number;
  minutos_sobreturno: number;
  ocupacion_porcentaje: string;
  sin_agenda: boolean;
  total_detalle: number;
  detalle_truncado: boolean;
  detalle: Fila[];
}

export interface ReporteAusentismo {
  atendidos: number;
  cancelados: number;
  ausentes: number;
  turnos_activos: number;
  tasa_ausentismo: string;
  tasa_no_asistencia: string;
  sin_cierres: boolean;
  total_detalle: number;
  detalle_truncado: boolean;
  detalle: Fila[];
}

export interface ReporteCaja {
  total_aprobado: string;
  total_efectivo: string;
  total_mercadopago: string;
  total_gastos: string;
  total_deudas: string;
  por_estado: Record<string, number>;
  total_detalle: number;
  detalle_truncado: boolean;
  detalle: Fila[];
  cajas: Fila[];
  movimientos: Fila[];
}

export interface ReporteLiquidaciones {
  cantidad_liquidaciones: number;
  total_cobertura: string;
  cantidad_practicas: number;
  por_estado: Fila[];
  por_obra_social: Fila[];
  por_prestacion: Fila[];
  total_detalle: number;
  detalle_truncado: boolean;
  detalle: Fila[];
}

export interface Exportacion {
  id: string;
  alcance: "paciente" | "consultorio";
  paciente_id: string | null;
  estado: "pendiente" | "generando" | "lista" | "fallida";
  tamano_bytes: number | null;
  generada_at: string | null;
  ultimo_error: string | null;
  intentos: number;
}

export interface FiltrosReporte {
  desde: string;
  hasta: string;
  limite: number;
  profesionalId?: string | null;
}

function query(params: Record<string, string | number | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  return search.toString();
}

function filtros(params: FiltrosReporte): Record<string, string | number | null> {
  return {
    desde: params.desde,
    hasta: params.hasta,
    limite: params.limite,
    profesional_id: params.profesionalId ?? null,
  };
}

export function fetchAgenda(params: FiltrosReporte): Promise<ReporteAgenda> {
  return fetchJson(
    `/reportes/agenda?${query(filtros(params))}`,
    authHeaders(),
  ) as Promise<ReporteAgenda>;
}

export function fetchAusentismo(
  params: FiltrosReporte,
): Promise<ReporteAusentismo> {
  return fetchJson(
    `/reportes/ausentismo?${query(filtros(params))}`,
    authHeaders(),
  ) as Promise<ReporteAusentismo>;
}

export function fetchCaja(params: FiltrosReporte): Promise<ReporteCaja> {
  return fetchJson(
    `/reportes/caja?${query({
      desde: params.desde,
      hasta: params.hasta,
      limite: params.limite,
    })}`,
    authHeaders(),
  ) as Promise<ReporteCaja>;
}

export function fetchLiquidaciones(
  params: FiltrosReporte,
): Promise<ReporteLiquidaciones> {
  return fetchJson(
    `/reportes/liquidaciones?${query({
      desde: params.desde,
      hasta: params.hasta,
      limite: params.limite,
    })}`,
    authHeaders(),
  ) as Promise<ReporteLiquidaciones>;
}

export function crearExportacion(
  alcance: "paciente" | "consultorio",
  pacienteId: string | null,
): Promise<Exportacion> {
  return postJson(
    "/exportaciones",
    {
      alcance,
      paciente_id: alcance === "paciente" ? pacienteId : null,
    },
    authHeaders(),
  ) as Promise<Exportacion>;
}

export function fetchExportacion(id: string): Promise<Exportacion> {
  return fetchJson(`/exportaciones/${id}`, authHeaders()) as Promise<Exportacion>;
}

export async function descargarExportacion(id: string): Promise<Blob> {
  const response = await fetch(`${getApiBaseUrl()}/exportaciones/${id}/archivo`, {
    headers: authHeaders(),
  });
  if (!response.ok) {
    const texto = await response.text();
    let cuerpo: unknown = texto;
    try {
      cuerpo = JSON.parse(texto) as unknown;
    } catch {
      cuerpo = texto;
    }
    throw new ApiError(response.status, cuerpo);
  }
  return response.blob();
}
