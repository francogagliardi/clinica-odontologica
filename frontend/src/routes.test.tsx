/**
 * C-17 route-level contract (design.md D5, D12): one h1 per route, the right
 * shell, the double-entry landing and a public 404 without protected nav.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { login, logout } from "./features/auth/session";

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/usuarios/login")) {
        return response({
          access_token: "jwt-routes",
          token_type: "bearer",
          expires_in: 1800,
          usuario: {
            id: "u-routes",
            nombre: "Carla Ruiz",
            email: "carla@clinica.test",
            roles: ["administrador"],
          },
        });
      }
      return response({ detail: "servicio no disponible en test" }, 500);
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

async function renderBackofficeAt(path: string): Promise<void> {
  await login("carla@clinica.test", "secreto");
  renderAt(path);
}

describe("rutas públicas", () => {
  it.each(["/", "/reservar", "/privacidad", "/reservar/gestion/token-1", "/ruta-inexistente"])(
    "%s renderiza un único h1 dentro del shell público",
    (path) => {
      renderAt(path);

      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
      expect(
        screen.getByRole("navigation", { name: "Navegación pública" }),
      ).toBeTruthy();
      expect(
        screen.queryByRole("navigation", { name: "Navegación principal" }),
      ).toBeNull();
      expect(document.querySelector(".ds-shell--public")).not.toBeNull();
    },
  );

  it("la portada ofrece reservar e ingresar como dos entradas", () => {
    renderAt("/");

    const reservar = screen.getByRole("link", { name: /reservar turno/i });
    const ingresar = screen.getByRole("link", {
      name: /ingresar al backoffice/i,
    });
    expect(reservar.getAttribute("href")).toBe("/reservar");
    expect(ingresar.getAttribute("href")).toBe("/agenda");
  });

  it("el 404 es público, sin navegación protegida", () => {
    renderAt("/no-existe");

    expect(
      screen.getByRole("heading", { level: 1, name: /no encontrada/i }),
    ).toBeTruthy();
    expect(screen.getByText(/404/)).toBeTruthy();
    for (const modulo of ["Agenda", "Reportes", "Usuarios", "Auditoría"]) {
      expect(screen.queryByRole("link", { name: modulo })).toBeNull();
    }
    expect(screen.getByRole("link", { name: "Reservar" })).toBeTruthy();
  });
});

describe("rutas de backoffice", () => {
  it.each([
    ["/agenda", /Agenda/],
    ["/reportes", /Reportes/],
    ["/usuarios", /Usuarios/],
    ["/auditoria", /Auditoría/],
  ])(
    "%s usa el shell de backoffice con un único h1",
    async (path, heading) => {
      await renderBackofficeAt(path);

      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
      expect(
        screen.getByRole("heading", { level: 1, name: heading }),
      ).toBeTruthy();
      expect(
        screen.getByRole("navigation", { name: "Navegación principal" }),
      ).toBeTruthy();
      expect(
        screen.queryByRole("navigation", { name: "Navegación pública" }),
      ).toBeNull();
      expect(document.querySelector(".ds-shell--backoffice")).not.toBeNull();
    },
  );

  it("sin sesión no expone enlaces protegidos", () => {
    renderAt("/reportes");

    expect(
      screen.getByRole("heading", { level: 1, name: /backoffice/i }),
    ).toBeTruthy();
    expect(screen.queryByRole("navigation")).toBeNull();
    expect(screen.queryByRole("button", { name: "Salir" })).toBeNull();
  });

  it.each(["/agenda", "/reportes", "/usuarios", "/auditoria"])(
    "%s sin sesión muestra el login centrado y sin rail",
    (path) => {
      renderAt(path);

      expect(document.querySelector("main.ds-auth")).not.toBeNull();
      expect(
        document.querySelector(".ds-auth__panel .ds-card"),
      ).not.toBeNull();
      expect(document.querySelector(".ds-shell--signed-out")).not.toBeNull();
      expect(screen.queryByRole("navigation")).toBeNull();
      expect(screen.queryByRole("button", { name: "Salir" })).toBeNull();
    },
  );
});
