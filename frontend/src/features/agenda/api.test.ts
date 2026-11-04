import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { login, logout } from "../auth/session";
import {
  fetchBloqueos,
  fetchTurnos,
  reprogramarTurno,
} from "./api";

const calls: Array<{ url: string; init?: RequestInit }> = [];

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
          usuario: { id: "u1", nombre: "R", email: "r@t", roles: ["recepcionista"] },
        });
      }
      if (url.includes("/turnos?")) {
        return response([]);
      }
      if (url.startsWith("http://api.test/bloqueos")) {
        return response([]);
      }
      if (url.includes("/reprogramar")) {
        return response({ id: "t1" });
      }
      throw new Error(`sin mock: ${url}`);
    }),
  );
  await login("r@test", "clave");
});

afterEach(() => {
  logout();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("agenda api", () => {
  it("manda el Bearer y los filtros de rango", async () => {
    await fetchTurnos("2026-11-09", "2026-11-15", "prof-1", null);
    const llamada = calls[calls.length - 1];
    expect(llamada?.url).toContain(
      "/turnos?desde=2026-11-09&hasta=2026-11-15&profesional_id=prof-1",
    );
    const headers = llamada?.init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer jwt-1");
  });

  it("consulta bloqueos con rango datetime", async () => {
    await fetchBloqueos("2026-11-09", "2026-11-15");
    expect(calls[calls.length - 1]?.url).toContain("desde=2026-11-09T00%3A00%3A00-03%3A00");
  });

  it("reprograma con PATCH e inicio ISO", async () => {
    await reprogramarTurno("turno-1", "2026-11-10T09:00:00-03:00");
    const llamada = calls[calls.length - 1];
    expect(llamada?.url).toContain("/turnos/turno-1/reprogramar");
    expect(llamada?.init?.method).toBe("PATCH");
    expect(llamada?.init?.body).toBe(
      JSON.stringify({ inicio: "2026-11-10T09:00:00-03:00" }),
    );
  });
});
