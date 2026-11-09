import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../shared/api/client";
import { login, logout } from "../auth/session";
import {
  actualizarUsuario,
  cambiarPassword,
  crearUsuario,
  fetchRoles,
  fetchUsuario,
  fetchUsuarios,
  reemplazarRoles,
} from "./api";

const calls: Array<{ url: string; init?: RequestInit }> = [];
let conflict = false;

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

function usuario(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: "u1",
    nombre: "Ana Demo",
    email: "ana@test",
    is_active: true,
    roles: ["odontologo"],
    ...overrides,
  };
}

beforeEach(async () => {
  vi.stubEnv("VITE_API_BASE_URL", "http://api.test");
  calls.length = 0;
  conflict = false;
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
            id: "admin",
            nombre: "Admin",
            email: "a@test",
            roles: ["administrador"],
          },
        });
      }
      if (url.endsWith("/roles")) {
        return response([
          { id: "r1", nombre: "administrador" },
          { id: "r2", nombre: "odontologo" },
        ]);
      }
      if (url.includes("/usuarios?")) {
        return response([usuario(), usuario({ id: "u2", is_active: false })]);
      }
      if (url.endsWith("/usuarios")) {
        if (init?.method === "POST") {
          if (conflict) {
            return response({ detail: "El email ya pertenece a otra cuenta" }, 409);
          }
          return response(usuario({ id: "u9" }), 201);
        }
        return response([
          usuario(),
          usuario({ id: "u2", is_active: false }),
        ]);
      }
      if (url.endsWith("/usuarios/u1")) {
        return response(usuario());
      }
      if (url.endsWith("/usuarios/u1/roles")) {
        return response(usuario({ roles: ["asistente", "odontologo"] }));
      }
      if (url.endsWith("/usuarios/u1/password")) {
        return response(usuario());
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

describe("usuarios api", () => {
  it("lista usuarios activos con Bearer y sin query por defecto", async () => {
    const usuarios = await fetchUsuarios();
    const llamada = calls[calls.length - 1];
    expect(llamada?.url.endsWith("/usuarios")).toBe(true);
    expect(usuarios).toHaveLength(2);
    const headers = llamada?.init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer jwt-1");
  });

  it("pide incluir_inactivos cuando se solicita", async () => {
    await fetchUsuarios(true);
    expect(calls[calls.length - 1]?.url).toContain(
      "incluir_inactivos=true",
    );
  });

  it("consulta el detalle y crea con POST autenticado", async () => {
    await fetchUsuario("u1");
    expect(calls[calls.length - 1]?.url.endsWith("/usuarios/u1")).toBe(true);

    const creado = await crearUsuario({
      nombre: "Nuevo",
      email: "nuevo@test",
      password: "clave-larga-123",
      roles: ["odontologo"],
    });
    const llamada = calls[calls.length - 1];
    expect(llamada?.url.endsWith("/usuarios")).toBe(true);
    expect(llamada?.init?.method).toBe("POST");
    expect(llamada?.init?.body).toBe(
      JSON.stringify({
        nombre: "Nuevo",
        email: "nuevo@test",
        password: "clave-larga-123",
        roles: ["odontologo"],
      }),
    );
    expect(creado.id).toBe("u9");
  });

  it("edita con PATCH, reemplaza roles con PUT y cambia la contraseña", async () => {
    await actualizarUsuario("u1", { activo: false });
    const patch = calls[calls.length - 1];
    expect(patch?.url.endsWith("/usuarios/u1")).toBe(true);
    expect(patch?.init?.method).toBe("PATCH");
    expect(patch?.init?.body).toBe(JSON.stringify({ activo: false }));

    await reemplazarRoles("u1", ["odontologo", "asistente"]);
    const put = calls[calls.length - 1];
    expect(put?.url.endsWith("/usuarios/u1/roles")).toBe(true);
    expect(put?.init?.method).toBe("PUT");
    expect(put?.init?.body).toBe(
      JSON.stringify({ roles: ["odontologo", "asistente"] }),
    );

    await cambiarPassword("u1", "otra-clave-456");
    const password = calls[calls.length - 1];
    expect(password?.url.endsWith("/usuarios/u1/password")).toBe(true);
    expect(password?.init?.method).toBe("POST");
    expect(password?.init?.body).toBe(
      JSON.stringify({ password: "otra-clave-456" }),
    );
  });

  it("lee el catálogo fijo de roles", async () => {
    const roles = await fetchRoles();
    expect(calls[calls.length - 1]?.url.endsWith("/roles")).toBe(true);
    expect(roles.map((rol) => rol.nombre)).toEqual([
      "administrador",
      "odontologo",
    ]);
  });

  it("propaga el 409 de un email duplicado sin reinterpretarlo", async () => {
    conflict = true;
    await expect(
      crearUsuario({
        nombre: "Nuevo",
        email: "ana@test",
        password: "clave-larga-123",
        roles: ["odontologo"],
      }),
    ).rejects.toBeInstanceOf(ApiError);
    await expect(
      crearUsuario({
        nombre: "Nuevo",
        email: "ana@test",
        password: "clave-larga-123",
        roles: ["odontologo"],
      }),
    ).rejects.toMatchObject({ status: 409 });
  });
});
