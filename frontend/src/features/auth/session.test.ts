import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getSession, login, logout } from "./session";

const USUARIO = {
  id: "user-1",
  nombre: "Recepción",
  email: "recep@test",
  roles: ["recepcionista"],
};

beforeEach(() => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  logout();
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("session", () => {
  it("guarda el token en memoria y no en storage", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            access_token: "jwt-123",
            token_type: "bearer",
            expires_in: 1800,
            usuario: USUARIO,
          }),
      })),
    );

    await login("recep@test", "clave");
    expect(getSession()?.token).toBe("jwt-123");
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("logout limpia la sesión", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        text: async () =>
          JSON.stringify({
            access_token: "jwt-123",
            token_type: "bearer",
            expires_in: 1800,
            usuario: USUARIO,
          }),
      })),
    );
    await login("recep@test", "clave");
    logout();
    expect(getSession()).toBeNull();
  });
});
