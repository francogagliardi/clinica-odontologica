import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../shared/api/client";
import { login, logout } from "../auth/session";
import { fetchAuditoria } from "./api";

const calls: Array<{ url: string; init?: RequestInit }> = [];
let forbidden = false;

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

beforeEach(async () => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  calls.length = 0;
  forbidden = false;
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
            nombre: "Auditor",
            email: "a@test",
            roles: ["auditor"],
          },
        });
      }
      if (url.includes("/auditoria")) {
        if (forbidden) {
          return response({ detail: "Permisos insuficientes" }, 403);
        }
        return response({
          total: 1,
          limite: 100,
          offset: 0,
          filas: [
            {
              id: "a1",
              usuario_id: "u1",
              usuario_email: "a@test",
              accion: "usuario.crear",
              entidad: "usuario",
              entidad_id: "u2",
              ip: "127.0.0.1",
              dispositivo: "vitest",
              timestamp: "2026-11-05T12:00:00-03:00",
            },
          ],
        });
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

describe("auditoria api", () => {
  it("envía filtros, paginación y Bearer", async () => {
    const resultado = await fetchAuditoria({
      usuarioId: "u1",
      entidad: "usuario",
      accion: "usuario.crear",
      desde: "2026-11-05",
      hasta: "2026-11-06",
      limite: 50,
      offset: 100,
    });
    const llamada = calls[calls.length - 1];
    const url = String(llamada?.url);
    expect(url).toContain("/auditoria?");
    expect(url).toContain("usuario_id=u1");
    expect(url).toContain("entidad=usuario");
    expect(url).toContain("accion=usuario.crear");
    expect(url).toContain("desde=2026-11-05");
    expect(url).toContain("hasta=2026-11-06");
    expect(url).toContain("limite=50");
    expect(url).toContain("offset=100");
    const headers = llamada?.init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer jwt-1");
    expect(resultado.total).toBe(1);
    expect(resultado.filas[0]?.accion).toBe("usuario.crear");
  });

  it("omite los filtros vacíos pero mantiene límite y offset", async () => {
    await fetchAuditoria({ limite: 100, offset: 0 });
    const url = String(calls[calls.length - 1]?.url);
    expect(url).not.toContain("usuario_id=");
    expect(url).not.toContain("entidad=");
    expect(url).toContain("limite=100");
    expect(url).toContain("offset=0");
  });

  it("propaga el 403 sin reinterpretarlo", async () => {
    forbidden = true;
    await expect(
      fetchAuditoria({ limite: 100, offset: 0 }),
    ).rejects.toBeInstanceOf(ApiError);
    await expect(
      fetchAuditoria({ limite: 100, offset: 0 }),
    ).rejects.toMatchObject({ status: 403 });
  });
});
