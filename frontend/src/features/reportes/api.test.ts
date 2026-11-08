import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../shared/api/client";
import { login, logout } from "../auth/session";
import {
  crearExportacion,
  descargarExportacion,
  fetchAgenda,
} from "./api";

const calls: Array<{ url: string; init?: RequestInit }> = [];
let archivoStatus = 200;

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
    blob: async () => new Blob([JSON.stringify(body)]),
  } as Response;
}

beforeEach(async () => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  calls.length = 0;
  archivoStatus = 200;
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
            id: "u1",
            nombre: "Admin",
            email: "a@test",
            roles: ["administrador"],
          },
        });
      }
      if (url.includes("/reportes/agenda?")) return response({});
      if (url.endsWith("/exportaciones") && init?.method === "POST") {
        return response({ id: "e1", estado: "pendiente" }, 202);
      }
      if (url.endsWith("/exportaciones/e1/archivo")) {
        return archivoStatus === 200
          ? response("zip")
          : response({ detail: "La exportación falló" }, archivoStatus);
      }
      throw new Error(`sin mock: ${url}`);
    }),
  );
  await login("a@test", "clave");
});

afterEach(() => {
  logout();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("reportes api", () => {
  it("envía Bearer, rango, límite y profesional", async () => {
    await fetchAgenda({
      desde: "2026-11-09",
      hasta: "2026-11-09",
      limite: 500,
      profesionalId: "prof-1",
    });
    const llamada = calls[calls.length - 1];
    expect(llamada?.url).toContain("/reportes/agenda?");
    expect(llamada?.url).toContain("desde=2026-11-09");
    expect(llamada?.url).toContain("hasta=2026-11-09");
    expect(llamada?.url).toContain("limite=500");
    expect(llamada?.url).toContain("profesional_id=prof-1");
    const headers = llamada?.init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer jwt-1");
  });

  it("crea una exportación con POST autenticado", async () => {
    const creada = await crearExportacion("paciente", "p1");
    const llamada = calls[calls.length - 1];
    expect(llamada?.url.endsWith("/exportaciones")).toBe(true);
    expect(llamada?.init?.method).toBe("POST");
    expect(llamada?.init?.body).toBe(
      JSON.stringify({ alcance: "paciente", paciente_id: "p1" }),
    );
    expect(creada.id).toBe("e1");
  });

  it("descarga el ZIP con Bearer y devuelve un Blob", async () => {
    const blob = await descargarExportacion("e1");
    const llamada = calls[calls.length - 1];
    expect(llamada?.url.endsWith("/exportaciones/e1/archivo")).toBe(true);
    const headers = llamada?.init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer jwt-1");
    expect(blob).toBeInstanceOf(Blob);
  });

  it("propaga el 409 de una descarga fallida sin inventar archivo", async () => {
    archivoStatus = 409;
    await expect(descargarExportacion("e1")).rejects.toBeInstanceOf(ApiError);
    await expect(descargarExportacion("e1")).rejects.toMatchObject({
      status: 409,
    });
  });
});
