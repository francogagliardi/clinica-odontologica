/**
 * C-17 public shell contract (design.md D5): sober header, public links only,
 * never session data or protected navigation.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { login, logout } from "../../features/auth/session";
import { PublicShell } from "./PublicShell";

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
    vi.fn(async () =>
      response({
        access_token: "jwt-public",
        token_type: "bearer",
        expires_in: 1800,
        usuario: {
          id: "u-2",
          nombre: "Bruno Gómez",
          email: "bruno@clinica.test",
          roles: ["administrador"],
        },
      }),
    ),
  );
});

afterEach(() => {
  logout();
  cleanup();
  vi.unstubAllGlobals();
});

describe("PublicShell", () => {
  it("muestra la marca y los enlaces públicos", () => {
    render(
      <PublicShell pathname="/reservar">
        <p>Formulario público</p>
      </PublicShell>,
    );

    expect(
      screen.getByRole("link", { name: "Clínica Odontológica" }).getAttribute(
        "href",
      ),
    ).toBe("/");
    expect(
      screen.getByRole("link", { name: "Reservar" }).getAttribute("href"),
    ).toBe("/reservar");
    expect(
      screen.getByRole("link", { name: "Privacidad" }).getAttribute("href"),
    ).toBe("/privacidad");
    expect(screen.getByText("Formulario público")).toBeTruthy();
  });

  it("no expone navegación protegida", () => {
    render(
      <PublicShell pathname="/privacidad">
        <p>Política</p>
      </PublicShell>,
    );

    expect(screen.queryByRole("link", { name: "Agenda" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Reportes" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Usuarios" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Auditoría" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Salir" })).toBeNull();
  });

  it("no imprime datos de sesión aunque exista una sesión en memoria", async () => {
    await login("bruno@clinica.test", "secreto");
    render(
      <PublicShell pathname="/reservar">
        <p>Formulario público</p>
      </PublicShell>,
    );

    expect(screen.queryByText("Bruno Gómez")).toBeNull();
    expect(screen.queryByText("bruno@clinica.test")).toBeNull();
  });

  it("el skip link apunta al contenido y el wrapper es enfocable", () => {
    render(
      <PublicShell pathname="/reservar">
        <p>Formulario público</p>
      </PublicShell>,
    );

    const skip = screen.getByRole("link", { name: "Saltar al contenido" });
    expect(screen.getAllByRole("link")[0]).toBe(skip);
    expect(
      document.getElementById("contenido")?.getAttribute("tabindex"),
    ).toBe("-1");
  });
});
