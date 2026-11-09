/**
 * C-17 integration: moving inside the backoffice must not reload the document,
 * because the JWT lives only in memory (R-03).
 */

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { getSession, login, logout } from "./features/auth/session";

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

const LOGIN = {
  access_token: "jwt-nav",
  token_type: "bearer",
  expires_in: 1800,
  usuario: {
    id: "u-nav",
    nombre: "Admin Demo",
    email: "admin@clinica.test",
    roles: ["administrador"],
  },
};

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  window.history.replaceState({}, "", "/agenda");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/usuarios/login")) return response(LOGIN);
      if (url.endsWith("/profesionales") || url.endsWith("/sillones")) {
        return response([]);
      }
      if (url.includes("/turnos?") || url.includes("/bloqueos?")) {
        return response([]);
      }
      if (url.includes("/reportes/agenda?")) {
        return response({
          total_turnos: 1,
          por_estado: {},
          cancelaciones: 0,
          minutos_disponibles: 60,
          minutos_ocupados: 30,
          minutos_sobreturno: 0,
          ocupacion_porcentaje: "50.00",
          sin_agenda: false,
          total_detalle: 0,
          detalle_truncado: false,
          detalle: [],
        });
      }
      if (url.includes("/reportes/ausentismo?")) {
        return response({
          atendidos: 0,
          cancelados: 0,
          ausentes: 0,
          turnos_activos: 0,
          tasa_ausentismo: "0",
          tasa_no_asistencia: "0",
          sin_cierres: false,
          total_detalle: 0,
          detalle_truncado: false,
          detalle: [],
        });
      }
      if (url.includes("/reportes/caja?")) {
        return response({
          total_aprobado: "0",
          total_efectivo: "0",
          total_mercadopago: "0",
          total_gastos: "0",
          total_deudas: "0",
          por_estado: {},
          total_detalle: 0,
          detalle_truncado: false,
          detalle: [],
          cajas: [],
          movimientos: [],
        });
      }
      if (url.includes("/reportes/liquidaciones?")) {
        return response({
          cantidad_liquidaciones: 0,
          total_cobertura: "0",
          cantidad_practicas: 0,
          por_estado: [],
          por_obra_social: [],
          por_prestacion: [],
          total_detalle: 0,
          detalle_truncado: false,
          detalle: [],
        });
      }
      throw new Error(`sin mock: ${url}`);
    }),
  );
});

afterEach(() => {
  cleanup();
  logout();
  window.history.replaceState({}, "", "/");
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("navegación interna del backoffice", () => {
  it("navega de Agenda a Reportes sin recargar y conserva la sesión", async () => {
    await login("admin@clinica.test", "demo-2026");
    render(<App />);

    expect(
      await screen.findByRole("heading", { level: 1, name: "Agenda" }),
    ).toBeTruthy();

    const nav = screen.getByRole("navigation", {
      name: "Navegación principal",
    });
    fireEvent.click(within(nav).getByRole("link", { name: "Reportes" }));

    expect(window.location.pathname).toBe("/reportes");
    expect(getSession()).not.toBeNull();
    expect(
      await screen.findByRole("heading", { level: 1, name: "Reportes" }),
    ).toBeTruthy();
    expect(await screen.findByText("Turnos totales: 1")).toBeTruthy();
    expect(
      screen.getByText("admin@clinica.test", { selector: ".ds-rail__session p" }),
    ).toBeTruthy();
  });

  it("vuelve a Agenda con el botón Atrás del navegador", async () => {
    await login("admin@clinica.test", "demo-2026");
    render(<App />);
    await screen.findByRole("heading", { level: 1, name: "Agenda" });

    const nav = screen.getByRole("navigation", {
      name: "Navegación principal",
    });
    fireEvent.click(within(nav).getByRole("link", { name: "Reportes" }));
    await screen.findByRole("heading", { level: 1, name: "Reportes" });

    window.history.back();

    await waitFor(() => {
      expect(window.location.pathname).toBe("/agenda");
    });
    expect(
      await screen.findByRole("heading", { level: 1, name: "Agenda" }),
    ).toBeTruthy();
    expect(getSession()).not.toBeNull();
  });
});
