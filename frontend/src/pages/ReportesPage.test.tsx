import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReportesPage } from "./ReportesPage";
import { login, logout } from "../features/auth/session";

const AGENDA = {
  total_turnos: 99,
  por_estado: { atendido: 3, cancelado: 1, ausente: 1 },
  cancelaciones: 1,
  minutos_disponibles: 480,
  minutos_ocupados: 240,
  minutos_sobreturno: 0,
  ocupacion_porcentaje: "50.00",
  sin_agenda: false,
  total_detalle: 1,
  detalle_truncado: false,
  detalle: [{ turno_id: "t1", estado: "atendido" }],
};

const AUSENTISMO = {
  atendidos: 6,
  cancelados: 2,
  ausentes: 2,
  turnos_activos: 5,
  tasa_ausentismo: "0.40",
  tasa_no_asistencia: "0.20",
  sin_cierres: false,
  total_detalle: 0,
  detalle_truncado: false,
  detalle: [],
};

const CAJA = {
  total_aprobado: "23000.00",
  total_efectivo: "15000.00",
  total_mercadopago: "8000.00",
  total_gastos: "3500.00",
  total_deudas: "12000.00",
  por_estado: { aprobado: 3 },
  total_detalle: 0,
  detalle_truncado: false,
  detalle: [],
  cajas: [],
  movimientos: [],
};

const LIQUIDACIONES = {
  cantidad_liquidaciones: 2,
  total_cobertura: "80000.00",
  cantidad_practicas: 4,
  por_estado: [],
  por_obra_social: [],
  por_prestacion: [{ prestacion_codigo: "OBT", cantidad: 2 }],
  total_detalle: 0,
  detalle_truncado: false,
  detalle: [],
};

const calls: Array<{ url: string; init?: RequestInit }> = [];
let agendaStatus = 200;
let exportPolls = 0;

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
    blob: async () => new Blob([JSON.stringify(body)]),
  } as Response;
}

function installFetch(): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push({ url, init });
      if (url.endsWith("/usuarios/login")) {
        return response({
          access_token: "jwt-1",
          token_type: "bearer",
          expires_in: 1800,
          usuario: {
            id: "u-admin",
            nombre: "Admin",
            email: "a@test",
            roles: ["administrador"],
          },
        });
      }
      if (url.includes("/reportes/agenda?")) {
        return agendaStatus === 200
          ? response(AGENDA)
          : response({ detail: "Permisos insuficientes" }, agendaStatus);
      }
      if (url.includes("/reportes/ausentismo?")) return response(AUSENTISMO);
      if (url.includes("/reportes/caja?")) return response(CAJA);
      if (url.includes("/reportes/liquidaciones?")) {
        return response(LIQUIDACIONES);
      }
      if (url.endsWith("/exportaciones") && init?.method === "POST") {
        return response({ id: "e1", estado: "pendiente" }, 202);
      }
      if (url.endsWith("/exportaciones/e1")) {
        exportPolls += 1;
        return response({
          id: "e1",
          estado: exportPolls === 1 ? "pendiente" : "lista",
        });
      }
      if (url.endsWith("/exportaciones/e1/archivo")) {
        return response("zip");
      }
      throw new Error(`sin mock: ${url}`);
    }),
  );
}

beforeEach(async () => {  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  calls.length = 0;
  agendaStatus = 200;
  exportPolls = 0;
  logout();
  installFetch();
  await login("a@test", "clave");
});

afterEach(() => {
  cleanup();
  logout();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("ReportesPage", () => {
  it("muestra los cuatro tableros con los totales de la API", async () => {
    render(<ReportesPage />);
    expect(await screen.findByText("Turnos totales: 99")).toBeTruthy();
    expect(screen.getByText("Atendidos: 6")).toBeTruthy();
    expect(screen.getByText("Total aprobado: 23000.00")).toBeTruthy();
    expect(screen.getByText("Liquidaciones: 2")).toBeTruthy();
    expect(screen.getByText("t1")).toBeTruthy();
  });

  it("muestra un 403 de la API verbatim", async () => {
    agendaStatus = 403;
    render(<ReportesPage />);
    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toContain("403");
    expect(alerta.textContent).toContain("Permisos insuficientes");
  });

  it("envía el rango y el límite elegidos", async () => {
    render(<ReportesPage />);
    await screen.findByText("Turnos totales: 99");
    fireEvent.change(screen.getByLabelText(/Desde/), {
      target: { value: "2026-11-10" },
    });
    await waitFor(() => {
      expect(
        calls.some((llamada) =>
          llamada.url.includes("desde=2026-11-10"),
        ),
      ).toBe(true);
    });
    fireEvent.change(screen.getByLabelText(/Límite/), {
      target: { value: "100" },
    });
    await waitFor(() => {
      expect(
        calls.some((llamada) => llamada.url.includes("limite=100")),
      ).toBe(true);
    });
  });

  it("exporta, sondea hasta lista y habilita la descarga", async () => {
    const createObjectURL = vi.fn(() => "blob:1");
    Object.defineProperty(URL, "createObjectURL", {
      value: createObjectURL,
      configurable: true,
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      value: vi.fn(),
      configurable: true,
    });
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);

    render(<ReportesPage />);
    await screen.findByText("Turnos totales: 99");
    fireEvent.change(screen.getByLabelText(/Paciente \(id\)/), {
      target: { value: "p1" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Exportar paciente" }),
    );
    expect(await screen.findByText("Estado: pendiente")).toBeTruthy();
    expect(
      (
        screen.getByRole("button", {
          name: "Descargar ZIP",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);

    await waitFor(
      () => expect(screen.getByText("Estado: lista")).toBeTruthy(),
      { timeout: 4000 },
    );
    const descarga = screen.getByRole("button", { name: "Descargar ZIP" });
    expect((descarga as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(descarga);
    await waitFor(() => {
      expect(
        calls.some((llamada) =>
          llamada.url.endsWith("/exportaciones/e1/archivo"),
        ),
      ).toBe(true);
    });
    expect(createObjectURL).toHaveBeenCalled();
    click.mockRestore();
  });
});
