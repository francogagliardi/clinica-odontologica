/** Date-only helpers for the agenda (UTC math, no timezone drift). */

export type Vista = "dia" | "semana" | "mes";

export interface Rango {
  desde: string;
  hasta: string;
}

function parse(fecha: string): Date {
  const [year, month, day] = fecha.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

function format(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function addDays(fecha: string, days: number): string {
  const date = parse(fecha);
  date.setUTCDate(date.getUTCDate() + days);
  return format(date);
}

export function hoyISO(): string {
  const now = new Date();
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
}

export function rango(vista: Vista, fecha: string): Rango {
  const date = parse(fecha);
  if (vista === "dia") {
    return { desde: fecha, hasta: fecha };
  }
  if (vista === "semana") {
    const offset = (date.getUTCDay() + 6) % 7; // Monday-first
    const lunes = new Date(date);
    lunes.setUTCDate(date.getUTCDate() - offset);
    return { desde: format(lunes), hasta: addDays(format(lunes), 6) };
  }
  const primero = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1));
  const ultimo = new Date(
    Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0),
  );
  return { desde: format(primero), hasta: format(ultimo) };
}

export function mover(vista: Vista, fecha: string, delta: number): string {
  if (vista === "dia") {
    return addDays(fecha, delta);
  }
  if (vista === "semana") {
    return addDays(fecha, delta * 7);
  }
  const date = parse(fecha);
  const primero = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1));
  primero.setUTCMonth(primero.getUTCMonth() + delta);
  return format(primero);
}

export function diasEntre(desde: string, hasta: string): string[] {
  const days: string[] = [];
  let cursor = desde;
  while (cursor <= hasta) {
    days.push(cursor);
    cursor = addDays(cursor, 1);
  }
  return days;
}

export function horaDe(inicioIso: string): string {
  return inicioIso.slice(11, 16);
}

export function fechaDe(inicioIso: string): string {
  return inicioIso.slice(0, 10);
}

export function inicioEnHora(fecha: string, hora: number): string {
  return `${fecha}T${String(hora).padStart(2, "0")}:00:00-03:00`;
}

export function inicioEnDia(fecha: string, inicioOriginal: string): string {
  return `${fecha}T${inicioOriginal.slice(11, 19)}-03:00`;
}
