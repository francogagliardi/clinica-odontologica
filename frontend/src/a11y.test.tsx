/**
 * C-17 structural accessibility contract (design.md D8, D12).
 *
 * jsdom cannot compute layout or contrast, so this file verifies what the
 * DOM can prove: one main/h1 per route, skip link first, table headers bound
 * with scope, scroll regions with an accessible name, field errors announced,
 * and focus styles present (never removed without replacement).
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { LoginForm } from "./features/auth/LoginForm";
import { login, logout } from "./features/auth/session";
import { AuditoriaPage } from "./pages/AuditoriaPage";
import { ReportesPage } from "./pages/ReportesPage";
import { UsuariosPage } from "./pages/UsuariosPage";
import appCss from "./styles/app.css?raw";

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

const LOGIN_OK = {
  access_token: "jwt-a11y",
  token_type: "bearer",
  expires_in: 1800,
  usuario: {
    id: "u-a11y",
    nombre: "Admin Demo",
    email: "admin@clinica.test",
    roles: ["administrador"],
  },
};

let fetchHandler: (url: string, init?: RequestInit) => Response | undefined;

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const handled = fetchHandler(url, init);
      if (handled !== undefined) {
        return handled;
      }
      throw new Error(`sin mock: ${url}`);
    }),
  );
});

afterEach(() => {
  logout();
  cleanup();
  vi.unstubAllGlobals();
});

function renderAt(path: string): void {
  window.history.pushState({}, "", path);
  render(<App />);
}

function expectRouteStructure(): void {
  expect(document.querySelectorAll("main")).toHaveLength(1);
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);

  const skip = document.querySelector("a.ds-skip");
  expect(skip).not.toBeNull();
  expect(skip?.getAttribute("href")).toBe("#contenido");
  const focusables = Array.from(
    document.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  );
  expect(focusables[0]).toBe(skip);
  expect(
    document.getElementById("contenido")?.getAttribute("tabindex"),
  ).toBe("-1");
}

function expectTableContract(): void {
  const tablas = screen.getAllByRole("table");
  expect(tablas.length).toBeGreaterThan(0);
  for (const tabla of tablas) {
    for (const th of Array.from(tabla.querySelectorAll("th"))) {
      expect(th.getAttribute("scope")).toBe("col");
    }
    const region = tabla.closest('[role="region"]');
    expect(region).not.toBeNull();
    expect(region?.getAttribute("aria-label")).toBeTruthy();
    expect(region?.getAttribute("tabindex")).toBe("0");
  }
}

describe("estructura accesible por ruta", () => {
  const publicas = [
    ["/", /clínica odontológica/i],
    ["/reservar", /reservar/i],
    ["/privacidad", /privacidad/i],
    ["/reservar/gestion/token-a11y", /mi turno/i],
    ["/ruta-inexistente", /no encontrada/i],
  ] as const;

  it.each(publicas)(
    "%s tiene un main, un h1 y el skip link primero",
    (path, heading) => {
      fetchHandler = (url) => {
        if (url.endsWith("/reservar/demo")) {
          return response({
            slug: "demo",
            nombre: "Consultorio Demo",
            profesionales: [],
            prestaciones: [],
            plazo_cancelacion_horas: 24,
            politica_cancelacion: "x",
            politica_sena: "y",
            moneda: "ARS",
          });
        }
        if (url.includes("/disponibilidad")) return response([]);
        if (url.endsWith("/privacidad")) {
          return response({
            version: "v1",
            vigente_desde: "2026-11-01",
            texto: "texto",
            hash: "b".repeat(64),
            alcance_legal_validado: false,
          });
        }
        return response({ detail: "no disponible" }, 500);
      };
      renderAt(path);

      expect(screen.getByRole("heading", { level: 1, name: heading })).toBeTruthy();
      expectRouteStructure();
    },
  );

  const backoffice = [
    ["/agenda", /agenda/i],
    ["/reportes", /reportes/i],
    ["/usuarios", /usuarios/i],
    ["/auditoria", /auditoría/i],
  ] as const;

  it.each(backoffice)(
    "%s tiene un main, un h1 y el skip link primero con sesión",
    async (path, heading) => {
      fetchHandler = (url) => {
        if (url.endsWith("/usuarios/login")) return response(LOGIN_OK);
        return response({ detail: "no disponible" }, 500);
      };
      await login("admin@clinica.test", "demo-2026");
      renderAt(path);

      expect(screen.getByRole("heading", { level: 1, name: heading })).toBeTruthy();
      expectRouteStructure();
    },
  );
});

describe("contrato de tablas", () => {
  it("reportes: encabezados con scope y regiones desplazables", async () => {
    fetchHandler = (url, init) => {
      if (url.endsWith("/usuarios/login")) return response(LOGIN_OK);
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
          total_detalle: 1,
          detalle_truncado: false,
          detalle: [{ turno_id: "t1", estado: "atendido" }],
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
      if (init?.method === "POST") return response({});
      return undefined;
    };
    await login("admin@clinica.test", "demo-2026");
    render(<ReportesPage />);
    await screen.findByText("Turnos totales: 1");
    expectTableContract();
  });

  it("usuarios: encabezados con scope y región con nombre", async () => {
    fetchHandler = (url) => {
      if (url.endsWith("/usuarios/login")) return response(LOGIN_OK);
      if (url.endsWith("/roles")) {
        return response([{ id: "r1", nombre: "administrador" }]);
      }
      if (url.includes("/usuarios?")) {
        return response([
          {
            id: "u1",
            nombre: "Ana Demo",
            email: "ana@test",
            is_active: true,
            roles: ["administrador"],
          },
        ]);
      }
      if (url.endsWith("/usuarios")) {
        return response([
          {
            id: "u1",
            nombre: "Ana Demo",
            email: "ana@test",
            is_active: true,
            roles: ["administrador"],
          },
        ]);
      }
      return response([]);
    };
    await login("admin@clinica.test", "demo-2026");
    render(<UsuariosPage />);
    await screen.findByText("Ana Demo");
    expectTableContract();
  });

  it("auditoría: encabezados con scope y región con nombre", async () => {
    fetchHandler = (url) => {
      if (url.endsWith("/usuarios/login")) return response(LOGIN_OK);
      if (url.includes("/auditoria")) {
        return response({
          total: 1,
          limite: 100,
          offset: 0,
          filas: [
            {
              id: "a1",
              usuario_id: "u1",
              usuario_email: "ana@test",
              accion: "usuario.crear",
              entidad: "usuario",
              entidad_id: "u2",
              ip: "127.0.0.1",
              dispositivo: "test",
              timestamp: "2026-11-08T12:00:00-03:00",
            },
          ],
        });
      }
      return response([]);
    };
    await login("admin@clinica.test", "demo-2026");
    render(<AuditoriaPage />);
    await screen.findByText("usuario.crear");
    expectTableContract();
  });
});

describe("errores de formulario accesibles", () => {
  it("el login marca aria-invalid y asocia el alert por aria-describedby", async () => {
    fetchHandler = () =>
      response({ detail: "Credenciales inválidas" }, 401);
    render(<LoginForm />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "admin@clinica.test" },
    });
    fireEvent.change(screen.getByLabelText("Contraseña"), {
      target: { value: "incorrecta" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Ingresar" }));

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toContain("401");
    await waitFor(() => {
      const email = screen.getByLabelText("Email");
      expect(email.getAttribute("aria-invalid")).toBe("true");
      const describedBy = email.getAttribute("aria-describedby");
      expect(describedBy).not.toBeNull();
      expect(document.getElementById(describedBy ?? "")).toBe(alerta);
    });
    expect(
      screen.getByLabelText("Contraseña").getAttribute("aria-invalid"),
    ).toBe("true");
  });
});

describe("foco visible", () => {
  it("la hoja declara :focus-visible y no elimina el contorno", () => {
    expect(appCss).toContain(":focus-visible");
    expect(appCss).not.toMatch(/outline:\s*(none|0)\b/);
  });
});
